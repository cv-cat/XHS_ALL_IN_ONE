from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    sub_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    external_user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    status_message: Mapped[str] = mapped_column(Text, default="")
    profile_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now, onupdate=shanghai_now)


class AccountCookieVersion(Base):
    __tablename__ = "account_cookie_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    encrypted_cookies: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
