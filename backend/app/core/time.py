from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
