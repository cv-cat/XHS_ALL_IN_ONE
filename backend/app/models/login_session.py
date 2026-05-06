from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    sub_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    login_method: Mapped[str] = mapped_column(String(32), default="qr")
    phone_mask: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    qr_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    qr_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_temp_cookies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
