from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import List


class PlatformId(str, Enum):
    XHS = "xhs"
    DOUYIN = "douyin"
    KUAISHOU = "kuaishou"
    WEIBO = "weibo"
    XIANYU = "xianyu"
    TAOBAO = "taobao"


@dataclass(frozen=True)
class PlatformMeta:
    id: PlatformId
    name_cn: str
    name_en: str
    enabled: bool
    status: str
    accent_color: str
    icon: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["id"] = self.id.value
        return payload


_PLATFORMS: List[PlatformMeta] = [
    PlatformMeta(PlatformId.XHS, "小红书", "XiaoHongShu", True, "enabled", "#ff2442", "xhs"),
    PlatformMeta(PlatformId.DOUYIN, "抖音", "Douyin", False, "coming_soon", "#111111", "douyin"),
    PlatformMeta(PlatformId.KUAISHOU, "快手", "Kuaishou", False, "coming_soon", "#ff7a00", "kuaishou"),
    PlatformMeta(PlatformId.WEIBO, "微博", "Weibo", False, "coming_soon", "#e6162d", "weibo"),
    PlatformMeta(PlatformId.XIANYU, "闲鱼", "Xianyu", False, "coming_soon", "#ffe100", "xianyu"),
    PlatformMeta(PlatformId.TAOBAO, "淘宝", "Taobao", False, "coming_soon", "#ff5000", "taobao"),
]


def get_platforms() -> List[PlatformMeta]:
    return list(_PLATFORMS)


def get_platform(platform_id: PlatformId) -> PlatformMeta:
    for platform in _PLATFORMS:
        if platform.id == platform_id:
            return platform
    raise KeyError(platform_id)
