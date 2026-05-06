from __future__ import annotations

import json
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.core.time import shanghai_now
from backend.app.models import KeywordGroup, Note, PlatformAccount, User
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/keyword-groups", tags=["keyword-groups"])


class KeywordGroupCreateRequest(BaseModel):
    platform: Literal["xhs", "douyin", "kuaishou", "weibo", "xianyu", "taobao"] = "xhs"
    name: str = Field(min_length=1, max_length=128)
    keywords: list[str] = Field(min_length=1, max_length=50)


class KeywordGroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    keywords: Optional[list[str]] = Field(default=None, min_length=1, max_length=50)


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        value = keyword.strip()
        key = value.lower()
        if value and key not in seen:
            normalized.append(value)
            seen.add(key)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one keyword is required")
    return normalized


def _serialize_group(group: KeywordGroup) -> dict[str, Any]:
    return {
        "id": group.id,
        "platform": group.platform,
        "name": group.name,
        "keywords": group.keywords or [],
        "created_at": group.created_at.isoformat(),
        "updated_at": group.updated_at.isoformat(),
    }


def _get_owned_group(db: Session, current_user: User, group_id: int) -> KeywordGroup:
    group = db.get(KeywordGroup, group_id)
    if group is None or group.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword group not found")
    return group


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "")
        multiplier = 1
        if cleaned.endswith("w"):
            multiplier = 10000
            cleaned = cleaned[:-1]
        try:
            return int(float(cleaned) * multiplier)
        except ValueError:
            return 0
    return 0


def _note_metrics(note: Note) -> dict[str, int]:
    raw = note.raw_json or {}
    interaction = raw.get("interact_info") if isinstance(raw.get("interact_info"), dict) else {}
    merged = {**raw, **interaction}
    likes = _as_int(merged.get("likes") or merged.get("liked_count") or merged.get("like_count"))
    collects = _as_int(merged.get("collects") or merged.get("collected_count") or merged.get("collect_count"))
    comments = _as_int(merged.get("comments") or merged.get("comment_count"))
    shares = _as_int(merged.get("shares") or merged.get("share_count"))
    return {
        "likes": likes,
        "collects": collects,
        "comments": comments,
        "shares": shares,
        "engagement": likes + collects + comments + shares,
    }


def _note_haystack(note: Note) -> str:
    raw_text = json.dumps(note.raw_json or {}, ensure_ascii=False)
    return "\n".join([note.note_id, note.title, note.content, note.author_name, raw_text]).lower()


def _owned_notes(db: Session, current_user: User, platform: str) -> list[Note]:
    return db.scalars(
        select(Note)
        .where(Note.user_id == current_user.id, Note.platform == platform)
        .order_by(Note.created_at.desc(), Note.id.desc())
    ).all()


def _trend_summary(db: Session, current_user: User, group: KeywordGroup) -> dict[str, Any]:
    notes = _owned_notes(db, current_user, group.platform)
    keyword_items: list[dict[str, Any]] = []
    matched_by_note_id: dict[int, dict[str, Any]] = {}
    for keyword in group.keywords or []:
        needle = keyword.lower()
        matched_notes = [note for note in notes if needle in _note_haystack(note)]
        engagement = sum(_note_metrics(note)["engagement"] for note in matched_notes)
        keyword_items.append({"keyword": keyword, "notes": len(matched_notes), "engagement": engagement})
        for note in matched_notes:
            metrics = _note_metrics(note)
            matched_by_note_id[note.id] = {
                "id": note.id,
                "note_id": note.note_id,
                "title": note.title,
                "author_name": note.author_name,
                "created_at": note.created_at.isoformat(),
                **metrics,
            }
    matched_notes = sorted(matched_by_note_id.values(), key=lambda item: item["engagement"], reverse=True)
    return {
        "total_matches": len(matched_notes),
        "total_engagement": sum(item["engagement"] for item in matched_notes),
        "keywords": keyword_items,
        "matched_notes": matched_notes[:10],
    }


@router.get("")
def list_keyword_groups(
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(KeywordGroup).where(KeywordGroup.user_id == current_user.id)
    if platform:
        statement = statement.where(KeywordGroup.platform == platform)
    groups = db.scalars(statement.order_by(KeywordGroup.created_at.desc(), KeywordGroup.id.desc())).all()
    return paginated([_serialize_group(group) for group in groups], page, page_size)


@router.post("")
def create_keyword_group(
    payload: KeywordGroupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = KeywordGroup(
        user_id=current_user.id,
        platform=payload.platform,
        name=payload.name.strip(),
        keywords=_normalize_keywords(payload.keywords),
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return _serialize_group(group)


@router.get("/{group_id}")
def get_keyword_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_owned_group(db, current_user, group_id)
    serialized = _serialize_group(group)
    serialized["trend"] = _trend_summary(db, current_user, group)
    return serialized


@router.patch("/{group_id}")
def update_keyword_group(
    group_id: int,
    payload: KeywordGroupUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_owned_group(db, current_user, group_id)
    if payload.name is not None:
        group.name = payload.name.strip()
    if payload.keywords is not None:
        group.keywords = _normalize_keywords(payload.keywords)
    group.updated_at = shanghai_now()
    db.commit()
    db.refresh(group)
    return _serialize_group(group)


@router.delete("/{group_id}")
def delete_keyword_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = _get_owned_group(db, current_user, group_id)
    db.delete(group)
    db.commit()
    return {"id": group_id, "status": "deleted"}
