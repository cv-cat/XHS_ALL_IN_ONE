from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.adapters.xhs.creator_api_adapter import XhsCreatorApiAdapter
from backend.app.core.database import SessionLocal
from backend.app.core.security import decrypt_text
from backend.app.core.time import shanghai_now
from backend.app.models import (
    AccountCookieVersion,
    AiDraft,
    AutoTask,
    ModelConfig,
    MonitoringSnapshot,
    MonitoringTarget,
    Note,
    Notification,
    PlatformAccount,
    PublishAsset,
    PublishJob,
    Task,
    User,
)


def _cookies_to_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    if stripped.startswith("{"):
        cookies = json.loads(stripped)
        return "; ".join(f"{key}={cookie_value}" for key, cookie_value in cookies.items())
    return stripped


def _latest_account_cookies(db: Session, account_id: int) -> str:
    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account_id)
        .order_by(AccountCookieVersion.created_at.desc(), AccountCookieVersion.id.desc())
    ).first()
    if cookie_version is None:
        raise RuntimeError("Account has no cookies")
    return _cookies_to_string(decrypt_text(cookie_version.encrypted_cookies))


def _asset_upload_info(asset: PublishAsset) -> dict[str, Any]:
    try:
        payload = json.loads(asset.creator_upload_info or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Uploaded asset metadata is invalid") from exc
    if not payload.get("fileIds"):
        raise RuntimeError("Uploaded asset is missing Creator upload info")
    return payload


def _external_note_id(payload: dict[str, Any]) -> str:
    for key in ("note_id", "noteId", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    data = payload.get("data")
    if isinstance(data, dict):
        return _external_note_id(data)
    return ""


def _serialize_publish_job(job: PublishJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "platform_account_id": job.platform_account_id,
        "source_draft_id": job.source_draft_id,
        "platform": job.platform,
        "title": job.title,
        "body": job.body,
        "publish_mode": job.publish_mode,
        "status": job.status,
        "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
        "external_note_id": job.external_note_id,
        "publish_error": job.publish_error,
        "published_at": job.published_at.isoformat() if job.published_at else None,
        "created_at": job.created_at.isoformat(),
    }


def _load_publish_options(job: PublishJob) -> dict[str, Any]:
    try:
        options = json.loads(job.publish_options or "{}")
    except json.JSONDecodeError:
        return {}
    return options if isinstance(options, dict) else {}


def _clean_topics(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [topic.strip() for topic in value if isinstance(topic, str) and topic.strip()]


def _apply_publish_options(note_info: dict[str, Any], options: dict[str, Any]) -> None:
    topics = _clean_topics(options.get("topics"))
    if topics:
        note_info["topics"] = topics
    location = options.get("location")
    if isinstance(location, str) and location.strip():
        note_info["location"] = location.strip()
    if options.get("privacy_type") in (0, 1):
        note_info["type"] = options["privacy_type"]


def _run_one_due_publish_job(db: Session, current_user: User, job: PublishJob, adapter_factory) -> tuple[bool, dict[str, Any]]:
    account = db.get(PlatformAccount, job.platform_account_id)
    if account is None or account.user_id != current_user.id:
        raise RuntimeError("Account not found")
    if account.platform != "xhs" or account.sub_type != "creator":
        raise RuntimeError("Creator account required")

    task = Task(
        user_id=current_user.id,
        platform=job.platform,
        task_type="creator_publish_scheduler",
        status="running",
        progress=20,
        payload={"publish_job_id": job.id, "platform_account_id": account.id, "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None},
    )
    db.add(task)
    job.status = "publishing"
    job.publish_error = ""
    db.commit()

    try:
        assets = db.scalars(
            select(PublishAsset).where(PublishAsset.publish_job_id == job.id).order_by(PublishAsset.id.asc())
        ).all()
        if any(asset.asset_type != "image" for asset in assets):
            raise RuntimeError("Only image publish is supported")
        uploaded_assets = [asset for asset in assets if asset.upload_status == "uploaded"]
        if not uploaded_assets:
            raise RuntimeError("At least one uploaded image asset is required")

        note_info = {
            "title": job.title,
            "desc": job.body,
            "media_type": "image",
            "image_file_infos": [_asset_upload_info(asset) for asset in uploaded_assets],
            "type": 1,
            "postTime": None,
        }
        _apply_publish_options(note_info, _load_publish_options(job))
        payload = adapter_factory(_latest_account_cookies(db, account.id)).post_note(note_info)
        job.status = "published"
        job.external_note_id = _external_note_id(payload)
        job.publish_error = ""
        job.published_at = shanghai_now()
        task.status = "completed"
        task.progress = 100
        task.payload = {**(task.payload or {}), "external_note_id": job.external_note_id, "published_at": job.published_at.isoformat()}
        db.commit()
        db.refresh(job)
        return True, _serialize_publish_job(job)
    except Exception as exc:
        job.status = "failed"
        job.publish_error = str(exc)
        task.status = "failed"
        task.progress = 100
        task.payload = {**(task.payload or {}), "error": str(exc)}
        db.commit()
        db.refresh(job)
        return False, _serialize_publish_job(job)


def run_due_publish_jobs(
    *,
    db: Session,
    current_user: User,
    now: Optional[datetime],
    platform: str,
    adapter_factory,
) -> dict[str, Any]:
    now = now or shanghai_now()
    due_jobs = db.scalars(
        select(PublishJob)
        .join(PlatformAccount, PublishJob.platform_account_id == PlatformAccount.id)
        .where(
            PlatformAccount.user_id == current_user.id,
            PublishJob.platform == platform,
            PublishJob.publish_mode == "scheduled",
            PublishJob.status == "pending",
            PublishJob.scheduled_at.is_not(None),
            PublishJob.scheduled_at <= now,
        )
        .order_by(PublishJob.scheduled_at.asc(), PublishJob.id.asc())
    ).all()

    items: list[dict[str, Any]] = []
    failed_count = 0
    for job in due_jobs:
        succeeded, item = _run_one_due_publish_job(db, current_user, job, adapter_factory)
        items.append(item)
        if not succeeded:
            failed_count += 1

    return {
        "executed_count": len(items),
        "failed_count": failed_count,
        "items": items,
    }


def run_due_publish_jobs_for_all_users(
    *,
    db: Session,
    now: Optional[datetime],
    platform: str,
    adapter_factory,
) -> dict[str, Any]:
    now = now or shanghai_now()
    users = db.scalars(
        select(User)
        .join(PlatformAccount, PlatformAccount.user_id == User.id)
        .join(PublishJob, PublishJob.platform_account_id == PlatformAccount.id)
        .where(
            PublishJob.platform == platform,
            PublishJob.publish_mode == "scheduled",
            PublishJob.status == "pending",
            PublishJob.scheduled_at.is_not(None),
            PublishJob.scheduled_at <= now,
        )
        .distinct()
        .order_by(User.id.asc())
    ).all()

    items: list[dict[str, Any]] = []
    failed_count = 0
    for user in users:
        result = run_due_publish_jobs(
            db=db,
            current_user=user,
            now=now,
            platform=platform,
            adapter_factory=adapter_factory,
        )
        items.extend(result["items"])
        failed_count += result["failed_count"]

    return {
        "executed_count": len(items),
        "failed_count": failed_count,
        "items": items,
    }


def run_due_publish_jobs_once(platform: str = "xhs", adapter_factory=XhsCreatorApiAdapter) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return run_due_publish_jobs_for_all_users(
            db=db,
            now=None,
            platform=platform,
            adapter_factory=adapter_factory,
        )
    finally:
        db.close()


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return 0


def _first_metric(raw: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw.get(key))
    return 0


def _note_metrics(note: Note) -> dict[str, int]:
    raw = note.raw_json or {}
    interaction = raw.get("interact_info") if isinstance(raw.get("interact_info"), dict) else {}
    merged = {**raw, **interaction}
    likes = _first_metric(merged, ("likes", "liked_count", "like_count", "likedCount"))
    collects = _first_metric(merged, ("collects", "collected_count", "collect_count", "collectedCount"))
    comments = _first_metric(merged, ("comments", "comment_count", "commentCount"))
    shares = _first_metric(merged, ("shares", "share_count", "shareCount"))
    return {
        "likes": likes,
        "collects": collects,
        "comments": comments,
        "shares": shares,
        "engagement": likes + collects + comments + shares,
    }


def _serialize_monitoring_note(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "note_id": note.note_id,
        "title": note.title,
        "author_name": note.author_name,
        "created_at": note.created_at.isoformat(),
        **_note_metrics(note),
    }


def _note_haystack(note: Note) -> str:
    raw_text = json.dumps(note.raw_json or {}, ensure_ascii=False)
    return "\n".join([note.note_id, note.title, note.content, note.author_name, raw_text]).lower()


def _note_matches_target(note: Note, target: MonitoringTarget) -> bool:
    needle = target.value.strip().lower()
    if not needle:
        return False
    return needle in _note_haystack(note)


def _matching_notes_for_target(db: Session, target: MonitoringTarget, platform: str) -> list[Note]:
    notes = db.scalars(
        select(Note)
        .where(
            Note.user_id == target.user_id,
            Note.platform == platform,
        )
        .order_by(Note.created_at.desc(), Note.id.desc())
    ).all()
    matched = [note for note in notes if _note_matches_target(note, target)]
    return sorted(matched, key=lambda note: _note_metrics(note)["engagement"], reverse=True)


def _refresh_monitoring_target(db: Session, target: MonitoringTarget, now: datetime, platform: str) -> dict[str, Any]:
    matched_notes = _matching_notes_for_target(db, target, platform)
    snapshot_payload = {
        "matched_count": len(matched_notes),
        "total_engagement": sum(_note_metrics(note)["engagement"] for note in matched_notes),
        "top_notes": [_serialize_monitoring_note(note) for note in matched_notes[:10]],
    }
    target.last_refreshed_at = now
    target.updated_at = now
    snapshot = MonitoringSnapshot(target_id=target.id, payload=snapshot_payload)
    db.add(snapshot)
    db.flush()

    task = Task(
        user_id=target.user_id,
        platform=platform,
        task_type="monitoring_refresh",
        status="completed",
        progress=100,
        payload={
            "target_id": target.id,
            "target_type": target.target_type,
            "value": target.value,
            "snapshot_id": snapshot.id,
            "matched_count": snapshot_payload["matched_count"],
            "scheduler": True,
        },
    )
    db.add(task)
    db.flush()
    return {
        "target_id": target.id,
        "snapshot_id": snapshot.id,
        "matched_count": snapshot_payload["matched_count"],
        "total_engagement": snapshot_payload["total_engagement"],
    }


def run_monitoring_refresh_for_all_users(*, db: Session, now: Optional[datetime], platform: str) -> dict[str, Any]:
    now = now or shanghai_now()
    targets = db.scalars(
        select(MonitoringTarget)
        .where(
            MonitoringTarget.platform == platform,
            MonitoringTarget.status == "active",
        )
        .order_by(MonitoringTarget.id.asc())
    ).all()

    items = [_refresh_monitoring_target(db, target, now, platform) for target in targets]
    db.commit()
    return {
        "refreshed_count": len(items),
        "items": items,
    }


def run_monitoring_refresh_once(platform: str = "xhs") -> dict[str, Any]:
    db = SessionLocal()
    try:
        return run_monitoring_refresh_for_all_users(db=db, now=None, platform=platform)
    finally:
        db.close()


def _get_text_model_for_user(db: Session, user_id: int):
    config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == user_id,
            ModelConfig.model_type == "text",
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if not config or not config.encrypted_api_key:
        return None, ""
    return config, decrypt_text(config.encrypted_api_key)


def _scheduler_cookies_to_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    if stripped.startswith("{"):
        cookies = json.loads(stripped)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    return stripped


def _execute_auto_task_background(db: Session, task: AutoTask) -> None:
    """Simplified auto-task execution for background scheduler."""
    import random

    from backend.app.adapters.xhs.pc_api_adapter import XhsPcApiAdapter
    from backend.app.api.platforms.xhs.crawl import _data_items
    from backend.app.api.platforms.xhs.pc import _normalize_search_item
    from backend.app.services.ai_service import OpenAICompatibleTextClient

    # Get PC cookies
    account = db.get(PlatformAccount, task.pc_account_id)
    if not account:
        return
    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()
    if not cookie_version:
        return
    cookies = _scheduler_cookies_to_string(decrypt_text(cookie_version.encrypted_cookies))

    # Pick keyword
    keywords = task.keywords or []
    if not keywords:
        return
    keyword = random.choice(keywords)

    # Search
    adapter = XhsPcApiAdapter(cookies)
    success, message, raw = adapter.search_note(keyword, page=1)
    if not success:
        return

    items = _data_items(raw)
    normalized = [_normalize_search_item(item) for item in items[:10]]
    if not normalized:
        return

    # Pick best
    best = max(
        normalized,
        key=lambda n: sum([n.get("likes", 0), n.get("collects", 0), n.get("comments", 0), n.get("shares", 0)]),
    )

    # Create draft
    draft = AiDraft(
        user_id=task.user_id,
        platform="xhs",
        title=best.get("title", ""),
        body=best.get("content", ""),
    )
    db.add(draft)
    db.flush()

    # Try AI rewrite title + body (non-fatal)
    try:
        model_config, api_key = _get_text_model_for_user(db, task.user_id)
        if model_config:
            client = OpenAICompatibleTextClient()
            instruction = task.ai_instruction or "改写为原创小红书笔记"
            rewritten_body = client.rewrite_note(
                model_config=model_config,
                api_key=api_key,
                title=draft.title,
                body=draft.body,
                instruction=instruction,
            )
            draft.body = rewritten_body
            try:
                titles = client.generate_titles(
                    model_config=model_config,
                    api_key=api_key,
                    title=draft.title,
                    body=draft.body,
                    count=1,
                )
                if titles:
                    draft.title = titles[0]
            except Exception:
                pass
    except Exception:
        pass

    # Get Creator cookies
    creator_account = db.get(PlatformAccount, task.creator_account_id)
    if not creator_account:
        return
    creator_cv = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == creator_account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()
    if not creator_cv:
        return
    creator_cookies = _scheduler_cookies_to_string(decrypt_text(creator_cv.encrypted_cookies))

    # Upload images and create publish job
    from backend.app.adapters.xhs.creator_api_adapter import XhsCreatorApiAdapter as AutoCreatorAdapter
    creator_adapter = AutoCreatorAdapter(creator_cookies)

    image_urls = (best.get("image_urls") or [])[:9]
    file_infos = []
    for url in image_urls:
        if not url:
            continue
        try:
            payload = creator_adapter.upload_media(url, "image")
            file_infos.append(payload)
        except Exception as exc:
            logger.warning(f"Auto task {task.id} image upload failed: {exc}")

    if not file_infos:
        return

    # Create publish job
    job = PublishJob(
        user_id=task.user_id,
        platform_account_id=task.creator_account_id,
        source_draft_id=draft.id,
        platform="xhs",
        title=draft.title,
        body=draft.body,
        publish_mode="immediate",
        status="publishing",
    )
    db.add(job)
    db.flush()

    for info in file_infos:
        db.add(PublishAsset(
            publish_job_id=job.id,
            asset_type="image",
            file_path="",
            upload_status="uploaded",
            creator_media_id=info.get("fileIds", ""),
            creator_upload_info=json.dumps(info, ensure_ascii=False),
        ))
    db.flush()

    # Publish via Creator API
    try:
        note_info = {
            "title": job.title,
            "desc": job.body,
            "media_type": "image",
            "image_file_infos": file_infos,
            "type": 1,
            "postTime": None,
        }
        result = creator_adapter.post_note(note_info)
        job.status = "published"
        job.external_note_id = ""
        for key in ("note_id", "noteId", "id"):
            v = result.get(key) or (result.get("data", {}) or {}).get(key)
            if v:
                job.external_note_id = str(v)
                break
        job.published_at = shanghai_now()
    except Exception as exc:
        job.status = "failed"
        job.publish_error = str(exc)[:500]
        logger.warning(f"Auto task {task.id} publish failed: {exc}")

    task.total_published = (task.total_published or 0) + 1
    task.last_run_at = shanghai_now()
    logger.info(f"Auto task {task.id} executed: keyword={keyword}, job={job.id}, status={job.status}")


def run_due_auto_tasks() -> None:
    from backend.app.api.auto_tasks import _calculate_next_run_at

    db = SessionLocal()
    try:
        now = shanghai_now()
        due_tasks = db.scalars(
            select(AutoTask).where(
                AutoTask.status == "active",
                AutoTask.schedule_type != "manual",
                AutoTask.next_run_at != None,  # noqa: E711
                AutoTask.next_run_at <= now,
            )
        ).all()

        for task in due_tasks:
            try:
                _execute_auto_task_background(db, task)
            except Exception as exc:
                logger.warning(f"Auto task {task.id} execution failed: {exc}")
            finally:
                # Always calculate next run
                _calculate_next_run_at(task)

        db.commit()
    except Exception as exc:
        logger.error(f"run_due_auto_tasks failed: {exc}")
    finally:
        db.close()


def _check_single_account(db: Session, account: PlatformAccount, now: datetime) -> str:
    """Check one account's cookie validity. Returns the new status."""
    from backend.app.adapters.xhs.pc_login_adapter import XhsPcLoginAdapter
    from backend.app.adapters.xhs.creator_login_adapter import XhsCreatorLoginAdapter
    from backend.app.services.account_service import decode_cookie_text

    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account.id)
        .order_by(AccountCookieVersion.created_at.desc())
    ).first()
    if cookie_version is None:
        account.status = "expired"
        account.status_message = "No stored cookie version"
        account.updated_at = now
        return "expired"

    adapter = XhsCreatorLoginAdapter() if account.sub_type == "creator" else XhsPcLoginAdapter()
    try:
        cookies_text = decrypt_text(cookie_version.encrypted_cookies)
        adapter.get_user_info(decode_cookie_text(cookies_text))
        old_status = account.status
        account.status = "active"
        account.status_message = ""
        account.updated_at = now
        return old_status
    except Exception as exc:
        old_status = account.status
        account.status = "expired"
        account.status_message = str(exc)
        account.updated_at = now
        return old_status


def check_all_account_cookies_once() -> None:
    """Scheduled job: check every account cookie, update status, notify on expiry."""
    db = SessionLocal()
    try:
        now = shanghai_now()
        accounts = db.scalars(select(PlatformAccount).order_by(PlatformAccount.id.asc())).all()
        checked = 0
        newly_expired = 0
        for account in accounts:
            try:
                old_status = _check_single_account(db, account, now)
                checked += 1
                if account.status == "expired" and old_status != "expired":
                    newly_expired += 1
                    db.add(Notification(
                        user_id=account.user_id,
                        title="账号 Cookie 过期",
                        body=f"账号「{account.nickname or account.external_user_id or account.id}」({account.sub_type or 'pc'}) Cookie 已失效，请重新绑定。",
                        level="warning",
                    ))
            except Exception as exc:
                logger.warning(f"Cookie check failed for account {account.id}: {exc}")
        db.commit()
        logger.info(f"Cookie check completed: {checked} accounts checked, {newly_expired} newly expired")
    except Exception as exc:
        logger.error(f"check_all_account_cookies_once failed: {exc}")
    finally:
        db.close()


def build_due_publish_scheduler(interval_seconds: int, job_func, monitoring_job_func=None) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        job_func,
        "interval",
        seconds=interval_seconds,
        id="due_publish_runner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        monitoring_job_func or job_func,
        "interval",
        seconds=interval_seconds,
        id="monitoring_refresh_runner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_due_auto_tasks,
        "interval",
        seconds=60,
        id="auto_tasks_runner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        check_all_account_cookies_once,
        "interval",
        hours=2,
        id="cookie_health_checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_due_publish_scheduler(interval_seconds: int) -> BackgroundScheduler:
    scheduler = build_due_publish_scheduler(
        interval_seconds=interval_seconds,
        job_func=run_due_publish_jobs_once,
        monitoring_job_func=run_monitoring_refresh_once,
    )
    scheduler.start()
    return scheduler


def shutdown_due_publish_scheduler(scheduler: Optional[BackgroundScheduler]) -> None:
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
