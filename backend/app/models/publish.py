from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("platform_accounts.id"), nullable=True, index=True)
    source_draft_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_drafts.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    publish_mode: Mapped[str] = mapped_column(String(32), default="immediate")
    publish_options: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    external_note_id: Mapped[str] = mapped_column(String(128), default="")
    publish_error: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)


class PublishAsset(Base):
    __tablename__ = "publish_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publish_job_id: Mapped[int] = mapped_column(ForeignKey("publish_jobs.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str] = mapped_column(Text)
    upload_status: Mapped[str] = mapped_column(String(32), default="pending")
    creator_media_id: Mapped[str] = mapped_column(String(128), default="")
    upload_error: Mapped[str] = mapped_column(Text, default="")
    creator_upload_info: Mapped[str] = mapped_column(Text, default="{}")
