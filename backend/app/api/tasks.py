from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.publish import get_creator_publish_adapter_factory
from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import Task, User
from backend.app.schemas.common import paginated
from backend.app.services.scheduler_service import run_due_publish_jobs

router = APIRouter(prefix="/tasks", tags=["tasks"])


def serialize_task(task: Task) -> dict:
    duration_ms = None
    if task.started_at and task.finished_at:
        duration_ms = int((task.finished_at - task.started_at).total_seconds() * 1000)
    return {
        "id": task.id,
        "platform": task.platform,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "payload": task.payload or {},
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "duration_ms": duration_ms,
        "error_type": task.error_type,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "parent_task_id": task.parent_task_id,
    }


def _get_owned_task(db: Session, current_user: User, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _is_scheduler_task(task: Task) -> bool:
    if task.task_type == "creator_publish_scheduler":
        return True
    if task.task_type == "monitoring_refresh":
        return bool((task.payload or {}).get("scheduler"))
    return False


@router.get("")
def get_tasks(
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Task).where(Task.user_id == current_user.id)
    if platform:
        statement = statement.where(Task.platform == platform)
    tasks = db.scalars(statement.order_by(Task.created_at.desc(), Task.id.desc())).all()
    return paginated([serialize_task(task) for task in tasks], page, page_size)


@router.post("/run-due")
def run_due_tasks(
    platform: str = Query("xhs"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_creator_publish_adapter_factory),
):
    return run_due_publish_jobs(
        db=db,
        current_user=current_user,
        now=None,
        platform=platform,
        adapter_factory=adapter_factory,
    )


@router.get("/scheduler/status")
def scheduler_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    scheduler = getattr(request.app.state, "scheduler", None)
    jobs = []
    if scheduler is not None:
        jobs = [
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ]
    scheduler_task_candidates = db.scalars(
        select(Task)
        .where(
            Task.user_id == current_user.id,
            Task.task_type.in_(("creator_publish_scheduler", "monitoring_refresh")),
        )
        .order_by(Task.created_at.desc(), Task.id.desc())
        .limit(50)
    ).all()
    recent_tasks = [task for task in scheduler_task_candidates if _is_scheduler_task(task)][:10]
    return {
        "enabled": settings.scheduler_enabled,
        "running": bool(scheduler is not None and scheduler.running),
        "interval_seconds": settings.scheduler_interval_seconds,
        "jobs": jobs,
        "recent_tasks": [serialize_task(task) for task in recent_tasks],
    }


@router.get("/{task_id}")
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(db, current_user, task_id)
    result = serialize_task(task)
    children = db.scalars(
        select(Task)
        .where(Task.parent_task_id == task.id, Task.user_id == current_user.id)
        .order_by(Task.created_at.asc())
    ).all()
    result["children"] = [serialize_task(c) for c in children]
    return result


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(db, current_user, task_id)
    if task.status in {"pending", "running"}:
        task.status = "cancelled"
        db.commit()
        db.refresh(task)
    return serialize_task(task)


@router.post("/{task_id}/retry")
def retry_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_owned_task(db, current_user, task_id)
    if task.status in {"failed", "exhausted"}:
        task.status = "pending"
        task.progress = 0
        task.retry_count = task.retry_count + 1
        task.error_type = None
        task.started_at = None
        task.finished_at = None
        db.commit()
        db.refresh(task)
    return serialize_task(task)
