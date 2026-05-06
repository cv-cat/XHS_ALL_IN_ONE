from __future__ import annotations

import random
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.platforms.xhs.crawl import _data_items, _normalize_search_item
from backend.app.api.platforms.xhs.pc import (
    _get_owned_pc_account_cookies,
    get_xhs_pc_api_adapter_factory,
)
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.security import decrypt_text
from backend.app.core.time import shanghai_now
from backend.app.models import (
    AccountCookieVersion,
    AiDraft,
    AutoTask,
    ModelConfig,
    PlatformAccount,
    PublishAsset,
    PublishJob,
    Task,
    User,
)
from backend.app.schemas.common import paginated
from backend.app.services.ai_service import OpenAICompatibleTextClient

router = APIRouter(prefix="/auto-tasks", tags=["auto-tasks"])


class AutoTaskCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    keywords: list[str] = Field(min_length=1)
    pc_account_id: int
    creator_account_id: int
    ai_instruction: str = Field(default="", max_length=2000)
    schedule_type: str = Field(default="manual", pattern="^(manual|daily|weekly|interval)$")
    schedule_time: str = Field(default="09:00", max_length=5)
    schedule_days: str = Field(default="", max_length=64)
    schedule_interval_hours: int = Field(default=24, ge=1, le=168)


class AutoTaskUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    keywords: Optional[list[str]] = None
    ai_instruction: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, pattern="^(active|paused|completed)$")
    schedule_type: Optional[str] = Field(default=None, pattern="^(manual|daily|weekly|interval)$")
    schedule_time: Optional[str] = Field(default=None, max_length=5)
    schedule_days: Optional[str] = Field(default=None, max_length=64)
    schedule_interval_hours: Optional[int] = Field(default=None, ge=1, le=168)


def _serialize_auto_task(task: AutoTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "name": task.name,
        "keywords": task.keywords or [],
        "pc_account_id": task.pc_account_id,
        "creator_account_id": task.creator_account_id,
        "ai_instruction": task.ai_instruction,
        "status": task.status,
        "schedule_type": task.schedule_type,
        "schedule_time": task.schedule_time,
        "schedule_days": task.schedule_days,
        "schedule_interval_hours": task.schedule_interval_hours,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "total_published": task.total_published,
        "created_at": task.created_at.isoformat(),
    }


def _get_owned_auto_task(db: Session, current_user: User, task_id: int) -> AutoTask:
    auto_task = db.scalars(
        select(AutoTask).where(AutoTask.id == task_id, AutoTask.user_id == current_user.id)
    ).first()
    if auto_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auto task not found")
    return auto_task


def _verify_account_ownership(db: Session, current_user: User, account_id: int, expected_sub_type: str) -> PlatformAccount:
    account = db.get(PlatformAccount, account_id)
    if (
        account is None
        or account.user_id != current_user.id
        or account.platform != "xhs"
        or account.sub_type != expected_sub_type
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"XHS {expected_sub_type} account not found",
        )
    return account


def _get_account_cookies(db: Session, account_id: int) -> str:
    from backend.app.api.publish import _cookies_to_string

    cookie_version = db.scalars(
        select(AccountCookieVersion)
        .where(AccountCookieVersion.platform_account_id == account_id)
        .order_by(AccountCookieVersion.created_at.desc(), AccountCookieVersion.id.desc())
    ).first()
    if cookie_version is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account has no cookies")
    return _cookies_to_string(decrypt_text(cookie_version.encrypted_cookies))


def _calculate_next_run_at(task: AutoTask) -> None:
    from datetime import timedelta
    now = shanghai_now()
    if task.schedule_type == "manual":
        task.next_run_at = None
    elif task.schedule_type == "daily":
        h, m = (task.schedule_time or "09:00").split(":")
        next_time = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(days=1)
        task.next_run_at = next_time
    elif task.schedule_type == "weekly":
        h, m = (task.schedule_time or "09:00").split(":")
        days = [int(d) for d in (task.schedule_days or "").split(",") if d.strip().isdigit()]
        if not days:
            task.next_run_at = None
            return
        for offset in range(1, 8):
            candidate = now + timedelta(days=offset)
            if candidate.isoweekday() in days:
                task.next_run_at = candidate.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
                return
    elif task.schedule_type == "interval":
        task.next_run_at = now + timedelta(hours=task.schedule_interval_hours)


@router.get("")
def list_auto_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = db.scalars(
        select(AutoTask)
        .where(AutoTask.user_id == current_user.id)
        .order_by(AutoTask.created_at.desc(), AutoTask.id.desc())
    ).all()
    return paginated([_serialize_auto_task(t) for t in tasks], page, page_size)


@router.post("")
def create_auto_task(
    payload: AutoTaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_account_ownership(db, current_user, payload.pc_account_id, "pc")
    _verify_account_ownership(db, current_user, payload.creator_account_id, "creator")

    auto_task = AutoTask(
        user_id=current_user.id,
        name=payload.name,
        keywords=payload.keywords,
        pc_account_id=payload.pc_account_id,
        creator_account_id=payload.creator_account_id,
        ai_instruction=payload.ai_instruction,
        schedule_type=payload.schedule_type,
        schedule_time=payload.schedule_time,
        schedule_days=payload.schedule_days,
        schedule_interval_hours=payload.schedule_interval_hours,
        status="active",
    )
    _calculate_next_run_at(auto_task)
    db.add(auto_task)
    db.commit()
    db.refresh(auto_task)
    return _serialize_auto_task(auto_task)


@router.patch("/{task_id}")
def update_auto_task(
    task_id: int,
    payload: AutoTaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auto_task = _get_owned_auto_task(db, current_user, task_id)

    if payload.name is not None:
        auto_task.name = payload.name
    if payload.keywords is not None:
        auto_task.keywords = payload.keywords
    if payload.ai_instruction is not None:
        auto_task.ai_instruction = payload.ai_instruction
    if payload.status is not None:
        auto_task.status = payload.status

    schedule_changed = False
    if payload.schedule_type is not None:
        auto_task.schedule_type = payload.schedule_type
        schedule_changed = True
    if payload.schedule_time is not None:
        auto_task.schedule_time = payload.schedule_time
        schedule_changed = True
    if payload.schedule_days is not None:
        auto_task.schedule_days = payload.schedule_days
        schedule_changed = True
    if payload.schedule_interval_hours is not None:
        auto_task.schedule_interval_hours = payload.schedule_interval_hours
        schedule_changed = True
    if schedule_changed:
        _calculate_next_run_at(auto_task)

    db.commit()
    db.refresh(auto_task)
    return _serialize_auto_task(auto_task)


@router.delete("/{task_id}")
def delete_auto_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auto_task = _get_owned_auto_task(db, current_user, task_id)
    db.delete(auto_task)
    db.commit()
    return {"id": task_id, "status": "deleted"}


@router.post("/{task_id}/run")
def run_auto_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    auto_task = _get_owned_auto_task(db, current_user, task_id)

    # Verify account ownership
    _verify_account_ownership(db, current_user, auto_task.pc_account_id, "pc")
    _verify_account_ownership(db, current_user, auto_task.creator_account_id, "creator")

    # Create a tracking task
    tracking_task = Task(
        user_id=current_user.id,
        platform="xhs",
        task_type="auto_ops_run",
        status="running",
        progress=10,
        payload={"auto_task_id": auto_task.id, "auto_task_name": auto_task.name},
    )
    db.add(tracking_task)
    db.flush()

    # 1. Pick a random keyword
    keywords = auto_task.keywords or []
    if not keywords:
        tracking_task.status = "failed"
        tracking_task.progress = 100
        tracking_task.payload = {**(tracking_task.payload or {}), "error": "No keywords configured"}
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No keywords configured")

    keyword = random.choice(keywords)
    tracking_task.payload = {**(tracking_task.payload or {}), "keyword": keyword}
    db.flush()

    # 2. Search notes using PC adapter
    pc_cookies = _get_owned_pc_account_cookies(db, current_user, auto_task.pc_account_id)
    adapter = adapter_factory(pc_cookies)
    success, message, raw_payload = adapter.search_note(keyword, page=1)
    if not success:
        tracking_task.status = "failed"
        tracking_task.progress = 100
        tracking_task.payload = {**(tracking_task.payload or {}), "error": message or "Search failed"}
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message or "XHS search failed")

    tracking_task.progress = 30
    db.flush()

    # 3. Normalize and pick top-engagement note
    items = _data_items(raw_payload)
    normalized_items = [_normalize_search_item(item) for item in items]
    if not normalized_items:
        tracking_task.status = "failed"
        tracking_task.progress = 100
        tracking_task.payload = {**(tracking_task.payload or {}), "error": "No notes found for keyword"}
        db.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No notes found for keyword")

    # Limit to crawl_count and pick best by engagement
    candidates = normalized_items[:10]
    best_note = max(
        candidates,
        key=lambda n: (n.get("likes", 0) + n.get("collects", 0) + n.get("comments", 0) + n.get("shares", 0)),
    )

    tracking_task.progress = 50
    tracking_task.payload = {
        **(tracking_task.payload or {}),
        "source_note_id": best_note.get("note_id"),
        "source_title": best_note.get("title"),
        "candidates_count": len(candidates),
    }
    db.flush()

    # 4. Create an AiDraft from the best note
    draft = AiDraft(
        user_id=current_user.id,
        platform="xhs",
        title=str(best_note.get("title") or ""),
        body=str(best_note.get("content") or ""),
    )
    db.add(draft)
    db.flush()

    tracking_task.progress = 60
    tracking_task.payload = {**(tracking_task.payload or {}), "draft_id": draft.id}
    db.flush()

    # 5. AI rewrite using the task's instruction
    model_config = db.scalars(
        select(ModelConfig).where(
            ModelConfig.user_id == current_user.id,
            ModelConfig.model_type == "text",
            ModelConfig.is_default.is_(True),
        )
    ).first()
    if model_config is None:
        tracking_task.status = "failed"
        tracking_task.progress = 100
        tracking_task.payload = {**(tracking_task.payload or {}), "error": "Default text model not configured"}
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default text model is not configured")

    api_key = decrypt_text(model_config.encrypted_api_key) if model_config.encrypted_api_key else ""
    text_client = OpenAICompatibleTextClient()

    try:
        rewritten_body = text_client.rewrite_note(
            model_config=model_config,
            api_key=api_key,
            title=draft.title,
            body=draft.body,
            instruction=auto_task.ai_instruction or "改写为原创小红书笔记，保持核心信息，提升表达和语感",
        )
        draft.body = rewritten_body
    except Exception as exc:
        tracking_task.status = "failed"
        tracking_task.progress = 100
        tracking_task.payload = {**(tracking_task.payload or {}), "error": f"AI rewrite failed: {exc}"}
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI rewrite failed: {exc}") from exc

    # 5b. Title rewrite (non-fatal)
    try:
        rewritten_title = text_client._complete(
            model_config=model_config,
            api_key=api_key,
            system_prompt="你是小红书标题创作专家。",
            user_prompt=f"为以下小红书笔记改写一个吸引人的标题（15字以内）：\n\n原标题：{draft.title}\n\n正文：{draft.body[:200]}",
            temperature=0.8,
        )
        draft.title = rewritten_title.strip().strip('"').strip("'").strip("《》")
    except Exception:
        pass  # title rewrite failure is not fatal

    tracking_task.progress = 80
    db.flush()

    # 6. Create a PublishJob with the Creator account
    publish_job = PublishJob(
        user_id=current_user.id,
        platform_account_id=auto_task.creator_account_id,
        source_draft_id=draft.id,
        platform="xhs",
        title=draft.title,
        body=draft.body,
        publish_mode="immediate",
        status="pending",
    )
    db.add(publish_job)
    db.flush()

    # 6b. Copy image assets from source note
    image_urls = best_note.get("image_urls", [])
    if isinstance(image_urls, list):
        for url in image_urls[:9]:  # max 9 images
            if isinstance(url, str) and url:
                db.add(PublishAsset(
                    publish_job_id=publish_job.id,
                    asset_type="image",
                    file_path=url,
                    upload_status="pending",
                ))

    # 7. Update auto task counters
    auto_task.total_published = (auto_task.total_published or 0) + 1
    auto_task.last_run_at = shanghai_now()
    _calculate_next_run_at(auto_task)

    tracking_task.status = "completed"
    tracking_task.progress = 100
    tracking_task.payload = {
        **(tracking_task.payload or {}),
        "publish_job_id": publish_job.id,
        "rewritten_length": len(rewritten_body),
    }

    db.commit()
    db.refresh(auto_task)
    db.refresh(draft)
    db.refresh(publish_job)

    return {
        "auto_task": _serialize_auto_task(auto_task),
        "keyword": keyword,
        "source_note": {
            "note_id": best_note.get("note_id"),
            "title": best_note.get("title"),
            "likes": best_note.get("likes", 0),
            "collects": best_note.get("collects", 0),
            "comments": best_note.get("comments", 0),
        },
        "draft": {
            "id": draft.id,
            "title": draft.title,
            "body": draft.body,
            "created_at": draft.created_at.isoformat(),
        },
        "publish_job": {
            "id": publish_job.id,
            "status": publish_job.status,
            "platform_account_id": publish_job.platform_account_id,
        },
    }
