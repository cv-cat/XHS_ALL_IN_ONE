import type { PlatformMeta } from "../types";

export const fallbackPlatforms: PlatformMeta[] = [
  { id: "xhs", name_cn: "小红书", name_en: "XiaoHongShu", enabled: true, status: "enabled", accent_color: "#ff2442", icon: "xhs" },
  { id: "douyin", name_cn: "抖音", name_en: "Douyin", enabled: false, status: "coming_soon", accent_color: "#111111", icon: "douyin" },
  { id: "kuaishou", name_cn: "快手", name_en: "Kuaishou", enabled: false, status: "coming_soon", accent_color: "#ff7a00", icon: "kuaishou" },
  { id: "weibo", name_cn: "微博", name_en: "Weibo", enabled: false, status: "coming_soon", accent_color: "#e6162d", icon: "weibo" },
  { id: "xianyu", name_cn: "闲鱼", name_en: "Xianyu", enabled: false, status: "coming_soon", accent_color: "#ffe100", icon: "xianyu" },
  { id: "taobao", name_cn: "淘宝", name_en: "Taobao", enabled: false, status: "coming_soon", accent_color: "#ff5000", icon: "taobao" }
];

export function getPlatform(id: string | undefined) {
  return fallbackPlatforms.find((platform) => platform.id === id) ?? fallbackPlatforms[0];
}
