from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, default=0)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    note_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(128), default="")
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)


class NoteAsset(Base):
    __tablename__ = "note_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(Text)
    local_path: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class NoteComment(Base):
    __tablename__ = "note_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), index=True)
    comment_id: Mapped[str] = mapped_column(String(128), index=True)
    user_name: Mapped[str] = mapped_column(String(128), default="")
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    parent_comment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at_remote: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(24), default="#111111")
