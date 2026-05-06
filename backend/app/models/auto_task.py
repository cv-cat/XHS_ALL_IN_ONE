from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class AutoTask(Base):
    __tablename__ = "auto_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pc_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    creator_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    ai_instruction: Mapped[str] = mapped_column(Text, default="")
    schedule_type: Mapped[str] = mapped_column(String(32), default="manual")
    schedule_time: Mapped[str] = mapped_column(String(32), default="09:00")
    schedule_days: Mapped[str] = mapped_column(String(64), default="")
    schedule_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_published: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
