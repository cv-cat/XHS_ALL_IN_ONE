from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory
from backend.app.api.tasks import serialize_task
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.time import shanghai_now
from backend.app.models import MonitoringSnapshot, MonitoringTarget, Note, PlatformAccount, Task, User
from backend.app.schemas.common import paginated
from backend.app.services.monitoring_crawl_service import execute_monitoring_refresh

router = APIRouter(prefix="/xhs/monitoring", tags=["xhs-monitoring"])


class MonitoringTargetCreateRequest(BaseModel):
    target_type: Literal["keyword", "account", "brand", "note_url"]
    name: str = Field(default="", max_length=128)
    value: str = Field(min_length=1, max_length=512)
    status: Literal["active", "paused"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)


class MonitoringTargetUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    value: Optional[str] = Field(default=None, min_length=1, max_length=512)
    status: Optional[Literal["active", "paused"]] = None
    config: Optional[dict[str, Any]] = None


def _serialize_target(target: MonitoringTarget) -> dict[str, Any]:
    return {
        "id": target.id,
        "platform": target.platform,
        "target_type": target.target_type,
        "name": target.name,
        "value": target.value,
        "status": target.status,
        "config": target.config or {},
        "last_refreshed_at": target.last_refreshed_at.isoformat() if target.last_refreshed_at else None,
        "created_at": target.created_at.isoformat(),
        "updated_at": target.updated_at.isoformat(),
        "platform_account_id": target.platform_account_id,
        "crawl_interval_minutes": target.crawl_interval_minutes,
        "consecutive_failures": target.consecutive_failures,
        "last_crawl_error": target.last_crawl_error,
    }


def _serialize_snapshot(snapshot: MonitoringSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "target_id": snapshot.target_id,
        "payload": snapshot.payload or {},
        "created_at": snapshot.created_at.isoformat(),
    }


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
    haystack = _note_haystack(note)
    return needle in haystack


def _matching_notes(db: Session, current_user: User, target: MonitoringTarget) -> list[Note]:
    notes = db.scalars(
        select(Note)
        .where(
            Note.user_id == current_user.id,
            Note.platform == "xhs",
        )
        .order_by(Note.created_at.desc(), Note.id.desc())
    ).all()
    matched = [note for note in notes if _note_matches_target(note, target)]
    return sorted(matched, key=lambda note: _note_metrics(note)["engagement"], reverse=True)


def _get_owned_target(db: Session, current_user: User, target_id: int) -> MonitoringTarget:
    target = db.get(MonitoringTarget, target_id)
    if target is None or target.user_id != current_user.id or target.platform != "xhs":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring target not found")
    return target


@router.get("/targets")
def targets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(MonitoringTarget)
        .where(MonitoringTarget.user_id == current_user.id, MonitoringTarget.platform == "xhs")
        .order_by(MonitoringTarget.created_at.desc(), MonitoringTarget.id.desc())
    ).all()
    return paginated([_serialize_target(target) for target in rows], page, page_size)


@router.post("/targets")
def create_target(
    payload: MonitoringTargetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = MonitoringTarget(
        user_id=current_user.id,
        platform="xhs",
        target_type=payload.target_type,
        name=payload.name or payload.value,
        value=payload.value,
        status=payload.status,
        config=payload.config,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return _serialize_target(target)


@router.patch("/targets/{target_id}")
def update_target(
    target_id: int,
    payload: MonitoringTargetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_target(db, current_user, target_id)
    if payload.name is not None:
        target.name = payload.name
    if payload.value is not None:
        target.value = payload.value
    if payload.status is not None:
        target.status = payload.status
    if payload.config is not None:
        target.config = payload.config
    target.updated_at = shanghai_now()
    db.commit()
    db.refresh(target)
    return _serialize_target(target)


@router.delete("/targets/{target_id}")
def delete_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_target(db, current_user, target_id)
    db.delete(target)
    db.commit()
    return {"id": target_id, "status": "deleted"}


@router.post("/targets/{target_id}/refresh")
def refresh_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    adapter_factory=Depends(get_xhs_pc_api_adapter_factory),
):
    target = _get_owned_target(db, current_user, target_id)
    return execute_monitoring_refresh(db, target, current_user, adapter_factory=adapter_factory)


@router.get("/targets/{target_id}/notes")
def target_notes(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_target(db, current_user, target_id)
    return {"target_id": target.id, "items": [_serialize_monitoring_note(note) for note in _matching_notes(db, current_user, target)]}


@router.get("/targets/{target_id}/snapshots")
def target_snapshots(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_target(db, current_user, target_id)
    snapshots = db.scalars(
        select(MonitoringSnapshot)
        .where(MonitoringSnapshot.target_id == target.id)
        .order_by(MonitoringSnapshot.created_at.desc(), MonitoringSnapshot.id.desc())
    ).all()
    return {"target_id": target.id, "items": [_serialize_snapshot(snapshot) for snapshot in snapshots]}
