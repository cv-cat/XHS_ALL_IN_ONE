from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import Notification, User
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/notifications", tags=["notifications"])


def serialize_notification(n: Notification) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "level": n.level,
        "source_task_id": n.source_task_id,
        "source_type": n.source_type,
        "source_id": n.source_id,
        "read": n.read,
        "created_at": n.created_at.isoformat(),
    }


@router.get("")
def list_notifications(
    unread: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread is True:
        stmt = stmt.where(Notification.read == False)
    items = db.scalars(stmt.order_by(Notification.created_at.desc())).all()
    return paginated([serialize_notification(n) for n in items], page, page_size)


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.read = True
    db.commit()
    db.refresh(n)
    return serialize_notification(n)


@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unread = db.scalars(
        select(Notification).where(Notification.user_id == current_user.id, Notification.read == False)
    ).all()
    for n in unread:
        n.read = True
    db.commit()
    return {"marked": len(unread)}
