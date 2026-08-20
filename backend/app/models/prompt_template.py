from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.time import shanghai_now


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(String(256), default="")
    topic_hint: Mapped[str] = mapped_column(Text, default="")
    reference_hint: Mapped[str] = mapped_column(Text, default="")
    instruction: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now)
