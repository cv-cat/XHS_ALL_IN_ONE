from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models import Tag, User, note_tags
from backend.app.schemas.common import paginated

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(default="#111111", max_length=24)


class TagUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    color: Optional[str] = Field(default=None, max_length=24)


def serialize_tag(tag: Tag) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
    }


def _normalize_name(name: str) -> str:
    return name.strip()


def _get_owned_tag(db: Session, current_user: User, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


def _ensure_unique_name(db: Session, current_user: User, name: str, exclude_tag_id: Optional[int] = None) -> None:
    statement = select(Tag).where(Tag.user_id == current_user.id, Tag.name == name)
    if exclude_tag_id is not None:
        statement = statement.where(Tag.id != exclude_tag_id)
    if db.scalars(statement).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name already exists")


@router.get("")
def list_tags(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tags = db.scalars(select(Tag).where(Tag.user_id == current_user.id).order_by(Tag.id.asc())).all()
    return paginated([serialize_tag(tag) for tag in tags], page, page_size)


@router.post("")
def create_tag(
    payload: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = _normalize_name(payload.name)
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name is required")
    _ensure_unique_name(db, current_user, name)
    tag = Tag(user_id=current_user.id, name=name, color=payload.color or "#111111")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return serialize_tag(tag)


@router.patch("/{tag_id}")
def update_tag(
    tag_id: int,
    payload: TagUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tag = _get_owned_tag(db, current_user, tag_id)
    if payload.name is not None:
        name = _normalize_name(payload.name)
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tag name is required")
        _ensure_unique_name(db, current_user, name, exclude_tag_id=tag.id)
        tag.name = name
    if payload.color is not None:
        tag.color = payload.color or "#111111"
    db.commit()
    db.refresh(tag)
    return serialize_tag(tag)


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tag = _get_owned_tag(db, current_user, tag_id)
    db.execute(delete(note_tags).where(note_tags.c.tag_id == tag.id))
    db.delete(tag)
    db.commit()
    return {"id": tag_id, "status": "deleted"}
