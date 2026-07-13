from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_admin
from backend.app.core.time import shanghai_now
from backend.app.models import (
    AiDraft,
    AiGeneratedAsset,
    ModelConfig,
    Note,
    PlatformAccount,
    PublishJob,
    Task,
    User,
)
from backend.app.schemas.common import paginated


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)
_PROCESS_STARTED_AT = time.monotonic()


class AdminUserUpdateRequest(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


def _lock_admin_user_update(db: Session, actor_id: int, target_id: int) -> dict[int, User]:
    if db.get_bind().dialect.name == "sqlite":
        db.rollback()
        db.execute(text("BEGIN IMMEDIATE"))
        statement = select(User)
    else:
        statement = select(User).with_for_update()
    locked_users = db.scalars(
        statement
        .where(or_(
            User.id.in_((actor_id, target_id)),
            (User.is_admin.is_(True) & User.is_active.is_(True)),
        ))
        .order_by(User.id.asc())
        .execution_options(populate_existing=True)
    ).all()
    return {user.id: user for user in locked_users}


def _count(db: Session, model, *criteria) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return int(db.scalar(statement) or 0)


def _serialize_user(db: Session, user: User) -> dict[str, Any]:
    platform_account_count = _count(db, PlatformAccount, PlatformAccount.user_id == user.id)
    content_count = (
        _count(db, Note, Note.user_id == user.id)
        + _count(db, AiDraft, AiDraft.user_id == user.id)
        + _count(db, AiGeneratedAsset, AiGeneratedAsset.user_id == user.id)
        + _count(db, PublishJob, PublishJob.user_id == user.id)
    )
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "platform_account_count": platform_account_count,
        "content_count": content_count,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _serialize_platform_account(account: PlatformAccount, username: str) -> dict[str, Any]:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "username": username,
        "platform": account.platform,
        "sub_type": account.sub_type,
        "external_user_id": account.external_user_id,
        "nickname": account.nickname,
        "avatar_url": account.avatar_url,
        "status": account.status,
        "status_message": account.status_message,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }


def _task_title(task: Task) -> str:
    payload = task.payload or {}
    return str(payload.get("title") or payload.get("name") or task.task_type)


def _serialize_task(task: Task, username: str) -> dict[str, Any]:
    payload = task.payload or {}
    updated_at = task.finished_at or task.started_at or task.created_at
    return {
        "id": task.id,
        "user_id": task.user_id,
        "username": username,
        "platform": task.platform,
        "task_type": task.task_type,
        "title": _task_title(task),
        "status": task.status,
        "progress": task.progress,
        "result_message": payload.get("error") or payload.get("message"),
        "publish_status": payload.get("publish_status"),
        "error_type": task.error_type,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "updated_at": updated_at.isoformat(),
    }


def _serialize_model_config(config: ModelConfig, username: str) -> dict[str, Any]:
    return {
        "id": config.id,
        "user_id": config.user_id,
        "username": username,
        "name": config.name,
        "model_type": config.model_type,
        "provider": config.provider,
        "model_name": config.model_name,
        "base_url": config.base_url,
        "has_api_key": bool(config.encrypted_api_key),
        "is_default": config.is_default,
        "status": "configured" if config.encrypted_api_key else "missing_key",
    }


def _recent_activity(db: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    task_rows = db.execute(
        select(Task, User.username)
        .outerjoin(User, User.id == Task.user_id)
        .order_by(Task.created_at.desc(), Task.id.desc())
        .limit(8)
    ).all()
    for task, username in task_rows:
        level = "error" if task.status in {"failed", "exhausted"} else "warning" if task.status in {"pending", "running"} else "info"
        items.append({
            "id": f"task:{task.id}",
            "event_type": "task",
            "actor": username or "unknown",
            "summary": f"{task.task_type} ({task.status})",
            "level": level,
            "created_at": task.created_at.isoformat(),
            "_created_at": task.created_at,
        })

    publish_rows = db.execute(
        select(PublishJob, User.username)
        .outerjoin(User, User.id == PublishJob.user_id)
        .order_by(PublishJob.created_at.desc(), PublishJob.id.desc())
        .limit(8)
    ).all()
    for job, username in publish_rows:
        level = "error" if job.status == "failed" else "warning" if job.status in {"pending", "scheduled", "publishing"} else "info"
        items.append({
            "id": f"publish:{job.id}",
            "event_type": "publish",
            "actor": username or "unknown",
            "summary": f"{job.title or '未命名发布'} ({job.status})",
            "level": level,
            "created_at": job.created_at.isoformat(),
            "_created_at": job.created_at,
        })

    items.sort(key=lambda item: item["_created_at"], reverse=True)
    for item in items[:10]:
        item.pop("_created_at", None)
    return items[:10]


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    now = shanghai_now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    account_healthy = PlatformAccount.status.in_(("active", "healthy"))
    account_risk = PlatformAccount.status.in_(("risk", "expired", "error"))
    content_total = sum(
        _count(db, model)
        for model in (Note, AiDraft, AiGeneratedAsset, PublishJob)
    )
    return {
        "generated_at": now.isoformat(),
        "users": {
            "total": _count(db, User),
            "active": _count(db, User, User.is_active.is_(True)),
            "new_today": _count(db, User, User.created_at >= start_of_day),
            "admins": _count(db, User, User.is_admin.is_(True)),
        },
        "platform_accounts": {
            "total": _count(db, PlatformAccount),
            "healthy": _count(db, PlatformAccount, account_healthy),
            "at_risk": _count(db, PlatformAccount, account_risk),
        },
        "content": {
            "total": content_total,
            "notes": _count(db, Note),
            "drafts": _count(db, AiDraft),
            "generated_assets": _count(db, AiGeneratedAsset),
            "publish_jobs": _count(db, PublishJob),
        },
        "tasks": {
            "running": _count(db, Task, Task.status == "running"),
            "queued": _count(db, Task, Task.status == "pending"),
            "failed_today": _count(
                db,
                Task,
                Task.status.in_(("failed", "exhausted")),
                Task.created_at >= start_of_day,
            ),
        },
        "publishes": {
            "pending": _count(db, PublishJob, PublishJob.status.in_(("pending", "scheduled"))),
            "published_today": _count(
                db,
                PublishJob,
                PublishJob.status == "published",
                PublishJob.published_at >= start_of_day,
            ),
            "failed_today": _count(
                db,
                PublishJob,
                PublishJob.status == "failed",
                PublishJob.created_at >= start_of_day,
            ),
        },
        "models": {
            "total": _count(db, ModelConfig),
            "configured": _count(db, ModelConfig, ModelConfig.encrypted_api_key != ""),
        },
        "recent_activity": _recent_activity(db),
    }


@router.get("/users")
def get_users(
    q: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(active|inactive|admin)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(User)
    if q and q.strip():
        statement = statement.where(User.username.ilike(f"%{q.strip()}%"))
    if status_filter == "active":
        statement = statement.where(User.is_active.is_(True))
    elif status_filter == "inactive":
        statement = statement.where(User.is_active.is_(False))
    elif status_filter == "admin":
        statement = statement.where(User.is_admin.is_(True))
    users = db.scalars(statement.order_by(User.created_at.desc(), User.id.desc())).all()
    return paginated([_serialize_user(db, user) for user in users], page, page_size)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if payload.is_admin is None and payload.is_active is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user changes supplied")
    current_admin_id = current_admin.id
    locked_users = _lock_admin_user_update(db, current_admin_id, user_id)
    current_admin = locked_users.get(current_admin_id)
    if current_admin is None or not current_admin.is_active or not current_admin.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    user = locked_users.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    proposed_admin = user.is_admin if payload.is_admin is None else payload.is_admin
    proposed_active = user.is_active if payload.is_active is None else payload.is_active
    if user.id == current_admin.id and not proposed_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrators cannot disable themselves")
    if user.id == current_admin.id and not proposed_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrators cannot revoke their own role")

    if user.is_admin and user.is_active and not (proposed_admin and proposed_active):
        other_effective_admins = sum(
            candidate.id != user.id and candidate.is_admin and candidate.is_active
            for candidate in locked_users.values()
        )
        if other_effective_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="At least one active administrator is required",
            )

    user.is_admin = proposed_admin
    user.is_active = proposed_active
    db.commit()
    db.refresh(user)
    return _serialize_user(db, user)


@router.get("/platform-accounts")
def get_platform_accounts(
    q: Optional[str] = None,
    platform: Optional[str] = None,
    account_status: Optional[str] = Query(default=None, alias="status"),
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(PlatformAccount, User.username).join(User, User.id == PlatformAccount.user_id)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        statement = statement.where(or_(PlatformAccount.nickname.ilike(needle), User.username.ilike(needle)))
    if platform:
        statement = statement.where(PlatformAccount.platform == platform)
    if account_status:
        statement = statement.where(PlatformAccount.status == account_status)
    if user_id is not None:
        statement = statement.where(PlatformAccount.user_id == user_id)
    rows = db.execute(statement.order_by(PlatformAccount.updated_at.desc(), PlatformAccount.id.desc())).all()
    return paginated([_serialize_platform_account(account, username) for account, username in rows], page, page_size)


def _content_rows(db: Session) -> list[dict[str, Any]]:
    usernames = {user.id: user.username for user in db.scalars(select(User)).all()}
    items: list[dict[str, Any]] = []
    for note in db.scalars(select(Note)).all():
        items.append({
            "id": note.id,
            "resource_key": f"note:{note.id}",
            "user_id": note.user_id,
            "username": usernames.get(note.user_id, "unknown"),
            "platform": note.platform,
            "content_type": "note",
            "title": note.title,
            "status": "saved",
            "created_at": note.created_at.isoformat(),
            "_created_at": note.created_at,
        })
    for draft in db.scalars(select(AiDraft)).all():
        items.append({
            "id": draft.id,
            "resource_key": f"draft:{draft.id}",
            "user_id": draft.user_id,
            "username": usernames.get(draft.user_id, "unknown"),
            "platform": draft.platform,
            "content_type": "draft",
            "title": draft.title,
            "status": "draft",
            "created_at": draft.created_at.isoformat(),
            "_created_at": draft.created_at,
        })
    for asset in db.scalars(select(AiGeneratedAsset)).all():
        items.append({
            "id": asset.id,
            "resource_key": f"generated_asset:{asset.id}",
            "user_id": asset.user_id,
            "username": usernames.get(asset.user_id, "unknown"),
            "platform": "xhs",
            "content_type": "generated_asset",
            "title": asset.prompt[:256],
            "status": "generated",
            "created_at": asset.created_at.isoformat(),
            "_created_at": asset.created_at,
        })
    for job in db.scalars(select(PublishJob)).all():
        items.append({
            "id": job.id,
            "resource_key": f"publish_job:{job.id}",
            "user_id": job.user_id,
            "username": usernames.get(job.user_id, "unknown"),
            "platform": job.platform,
            "content_type": "publish_job",
            "title": job.title,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "_created_at": job.created_at,
        })
    return items


@router.get("/content/summary")
def get_content_summary(db: Session = Depends(get_db)):
    publish_statuses = dict(
        db.execute(select(PublishJob.status, func.count()).group_by(PublishJob.status)).all()
    )
    return {
        "total": sum(_count(db, model) for model in (Note, AiDraft, AiGeneratedAsset, PublishJob)),
        "notes": _count(db, Note),
        "drafts": _count(db, AiDraft),
        "generated_assets": _count(db, AiGeneratedAsset),
        "publish_jobs": _count(db, PublishJob),
        "publish_statuses": publish_statuses,
    }


@router.get("/content")
def get_content(
    q: Optional[str] = None,
    content_status: Optional[str] = Query(default=None, alias="status"),
    content_type: Optional[str] = Query(default=None, alias="type"),
    user_id: Optional[int] = None,
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items = _content_rows(db)
    if q and q.strip():
        needle = q.strip().lower()
        items = [item for item in items if needle in item["title"].lower() or needle in item["username"].lower()]
    if content_status:
        items = [item for item in items if item["status"] == content_status]
    if content_type:
        normalized_type = "publish_job" if content_type == "publish" else content_type
        items = [item for item in items if item["content_type"] == normalized_type]
    if user_id is not None:
        items = [item for item in items if item["user_id"] == user_id]
    if platform:
        items = [item for item in items if item["platform"] == platform]
    items.sort(key=lambda item: (item["_created_at"], item["resource_key"]), reverse=True)
    for item in items:
        item.pop("_created_at", None)
    return paginated(items, page, page_size)


@router.get("/tasks")
def get_tasks(
    q: Optional[str] = None,
    task_status: Optional[str] = Query(default=None, alias="status"),
    task_type: Optional[str] = Query(default=None, alias="type"),
    platform: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(Task, User.username).join(User, User.id == Task.user_id)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        search_criteria = [Task.task_type.ilike(needle), User.username.ilike(needle)]
        if q.strip().isdigit():
            search_criteria.append(Task.id == int(q.strip()))
        statement = statement.where(or_(*search_criteria))
    if task_status:
        statement = statement.where(Task.status == task_status)
    if task_type == "ai":
        statement = statement.where(Task.task_type.ilike("ai_%"))
    elif task_type == "auto_ops":
        statement = statement.where(Task.task_type.ilike("auto_ops%"))
    elif task_type == "crawl":
        statement = statement.where(Task.task_type.ilike("%crawl%"))
    elif task_type == "publish":
        statement = statement.where(Task.task_type.ilike("%publish%"))
    elif task_type == "monitoring":
        statement = statement.where(Task.task_type.ilike("monitoring_%"))
    elif task_type:
        statement = statement.where(Task.task_type == task_type)
    if platform:
        statement = statement.where(Task.platform == platform)
    if user_id is not None:
        statement = statement.where(Task.user_id == user_id)
    rows = db.execute(statement.order_by(Task.created_at.desc(), Task.id.desc())).all()
    return paginated([_serialize_task(task, username) for task, username in rows], page, page_size)


@router.get("/model-configs")
def get_model_configs(
    q: Optional[str] = None,
    model_status: Optional[str] = Query(default=None, alias="status", pattern="^(configured|missing_key|default)$"),
    model_type: Optional[str] = Query(default=None, alias="type", pattern="^(text|image)$"),
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    statement = select(ModelConfig, User.username).join(User, User.id == ModelConfig.user_id)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        statement = statement.where(or_(
            ModelConfig.name.ilike(needle),
            ModelConfig.model_name.ilike(needle),
            ModelConfig.provider.ilike(needle),
            User.username.ilike(needle),
        ))
    if model_status == "configured":
        statement = statement.where(ModelConfig.encrypted_api_key != "")
    elif model_status == "missing_key":
        statement = statement.where(ModelConfig.encrypted_api_key == "")
    elif model_status == "default":
        statement = statement.where(ModelConfig.is_default.is_(True))
    if model_type:
        statement = statement.where(ModelConfig.model_type == model_type)
    if user_id is not None:
        statement = statement.where(ModelConfig.user_id == user_id)
    rows = db.execute(statement.order_by(ModelConfig.id.desc())).all()
    return paginated([_serialize_model_config(config, username) for config, username in rows], page, page_size)


@router.get("/system-health")
def get_system_health(request: Request, db: Session = Depends(get_db)):
    checked_at = shanghai_now()
    database_started = time.perf_counter()
    database_status = "healthy"
    database_message = None
    try:
        db.scalar(select(1))
    except Exception as exc:
        database_status = "down"
        database_message = str(exc)[:200]
    database_latency_ms = round((time.perf_counter() - database_started) * 1000, 2)

    settings = get_settings()
    scheduler = getattr(request.app.state, "scheduler", None)
    scheduler_running = bool(scheduler is not None and scheduler.running)
    scheduler_status = "healthy" if (not settings.scheduler_enabled or scheduler_running) else "down"
    scheduler_message = "running" if scheduler_running else "disabled" if not settings.scheduler_enabled else "not running"
    if database_status == "healthy":
        queue = {
            "status": "healthy",
            "pending": _count(db, Task, Task.status == "pending"),
            "running": _count(db, Task, Task.status == "running"),
            "failed": _count(db, Task, Task.status.in_(("failed", "exhausted"))),
        }
    else:
        db.rollback()
        queue = {"status": "down", "pending": 0, "running": 0, "failed": 0}
    overall_status = (
        "down" if database_status == "down"
        else "healthy" if scheduler_status == "healthy"
        else "degraded"
    )
    return {
        "status": overall_status,
        "checked_at": checked_at.isoformat(),
        "version": "dev",
        "uptime_seconds": int(time.monotonic() - _PROCESS_STARTED_AT),
        "database": {
            "status": database_status,
            "latency_ms": database_latency_ms,
            "message": database_message,
        },
        "queue": queue,
        "services": [
            {"name": "api", "status": "healthy", "message": "request accepted"},
            {
                "name": "database",
                "status": database_status,
                "latency_ms": database_latency_ms,
                "message": database_message,
            },
            {"name": "scheduler", "status": scheduler_status, "message": scheduler_message},
        ],
    }
