import { Result } from "antd";
import { useParams } from "react-router-dom";

const sectionInfo: Record<string, { title: string; description: string }> = {
  accounts: {
    title: "账号矩阵",
    description: "管理 PC 与 Creator 账号、Cookie 状态、健康检查和账号作用域。",
  },
  discovery: {
    title: "笔记发现",
    description: "关键词搜索、URL 直达、账号笔记抓取和批量入库会在这里汇合。",
  },
  library: {
    title: "内容库",
    description: "视觉笔记卡、标签、筛选、批量导出和素材下载的统一资产库。",
  },
  analytics: {
    title: "数据洞察",
    description: "围绕已抓取数据生成趋势、爆款拆解、评论痛点和关键词机会。",
  },
  benchmarks: {
    title: "竞品监控",
    description: "跟踪目标账号、品牌、关键词与 URL 的最新变化和内容模式。",
  },
  rewrite: {
    title: "AI 改写",
    description: "把收藏笔记转化为可编辑草稿，生成标题、标签和内容角度。",
  },
  "image-studio": {
    title: "图片工坊",
    description: "封面生成、配图变体、版式调整和发布前图片处理。",
  },
  publish: {
    title: "发布中心",
    description: "草稿、素材上传、立即发布、定时发布、失败重试和历史记录。",
  },
};

export function XhsSectionPage() {
  const { section = "discovery" } = useParams();
  const info = sectionInfo[section] ?? sectionInfo.discovery;

  return (
    <Result
      status="info"
      title={info.title}
      subTitle={info.description}
    />
  );
}
