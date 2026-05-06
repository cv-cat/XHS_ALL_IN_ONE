import {
  BarChartOutlined,
  CommentOutlined,
  DownloadOutlined,
  FileTextOutlined,
  FireOutlined,
  ReloadOutlined,
  TagsOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  List,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  createXhsAnalyticsReport,
  downloadExportFile,
  fetchXhsCommentInsights,
  fetchXhsHotTopics,
  fetchXhsOverview,
  fetchXhsTopContent,
} from "../../../lib/api";
import type {
  AnalyticsCommentInsight,
  AnalyticsHotTopic,
  AnalyticsTopContent,
  DashboardOverview,
} from "../../../types";

const { Text } = Typography;

const fallbackOverview: DashboardOverview = {
  platform: "xhs",
  today_crawls: 0,
  saved_notes: 0,
  pending_publishes: 0,
  healthy_accounts: 0,
  at_risk_accounts: 0,
  comment_count: 0,
  total_engagement: 0,
  hot_topics: [],
  recent_activity: [],
};

const fallbackComments: AnalyticsCommentInsight = {
  total_comments: 0,
  question_count: 0,
  top_terms: [],
  top_comments: [],
};

function formatNumber(value = 0): string {
  return value.toLocaleString();
}

const topContentColumns: ColumnsType<AnalyticsTopContent> = [
  {
    title: "标题",
    dataIndex: "title",
    key: "title",
    ellipsis: true,
    render: (text: string, record: AnalyticsTopContent) => text || record.note_id,
  },
  {
    title: "作者",
    dataIndex: "author_name",
    key: "author_name",
    width: 120,
    render: (text: string) => text || "-",
  },
  {
    title: "赞藏评转",
    key: "stats",
    width: 200,
    render: (_: unknown, record: AnalyticsTopContent) =>
      `${formatNumber(record.likes)} / ${formatNumber(record.collects)} / ${formatNumber(record.comments)} / ${formatNumber(record.shares)}`,
  },
  {
    title: "互动",
    dataIndex: "engagement",
    key: "engagement",
    width: 100,
    render: (value: number) => formatNumber(value),
    sorter: (a: AnalyticsTopContent, b: AnalyticsTopContent) => a.engagement - b.engagement,
  },
];

const metricIconColors = ["#1668dc", "#52c41a", "#faad14", "#eb2f96"];

export function XhsAnalyticsPage() {
  const [overview, setOverview] = useState<DashboardOverview>(fallbackOverview);
  const [topContent, setTopContent] = useState<AnalyticsTopContent[]>([]);
  const [hotTopics, setHotTopics] = useState<AnalyticsHotTopic[]>([]);
  const [commentInsights, setCommentInsights] =
    useState<AnalyticsCommentInsight>(fallbackComments);
  const [isLoading, setIsLoading] = useState(true);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportMessage, setReportMessage] = useState<string | null>(null);

  async function loadAnalytics() {
    setIsLoading(true);
    setError(null);
    try {
      const [overviewResult, topResult, topicsResult, commentsResult] =
        await Promise.all([
          fetchXhsOverview(),
          fetchXhsTopContent(),
          fetchXhsHotTopics(),
          fetchXhsCommentInsights(),
        ]);
      setOverview(overviewResult);
      setTopContent(topResult.items);
      setHotTopics(topicsResult.items);
      setCommentInsights(commentsResult);
    } catch {
      setError("数据洞察加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadAnalytics();
  }, []);

  async function generateReport() {
    setIsGeneratingReport(true);
    setError(null);
    setReportMessage(null);
    try {
      const report = await createXhsAnalyticsReport({ format: "json" });
      await downloadExportFile(report.download_url, report.file_name);
      setReportMessage(`已生成运营报告：${report.note_count} 篇笔记`);
    } catch {
      setError("运营报告生成失败，请稍后重试。");
    } finally {
      setIsGeneratingReport(false);
    }
  }

  const metrics = [
    { label: "内容库笔记", value: overview.saved_notes, icon: <FileTextOutlined /> },
    { label: "总互动", value: overview.total_engagement ?? 0, icon: <BarChartOutlined /> },
    { label: "已存评论", value: overview.comment_count ?? 0, icon: <CommentOutlined /> },
    { label: "话题数", value: hotTopics.length, icon: <TagsOutlined /> },
  ];

  const maxTopicEngagement = hotTopics.length > 0
    ? Math.max(...hotTopics.map((t) => t.engagement))
    : 1;

  const termSizes = [18, 16, 15, 14, 13, 12];

  return (
    <div>
      <Alert type="info" showIcon message="数据洞察模块正在开发优化中，当前为基础版本，更多分析维度即将上线。" style={{ marginBottom: 16 }} />
      <PageHeader
        eyebrow="XHS Analytics"
        title="数据洞察"
        description="基于已保存笔记、标签和评论生成可执行的内容机会视图。"
        action={
          <Space>
            <Button
              icon={<DownloadOutlined />}
              onClick={generateReport}
              loading={isGeneratingReport}
            >
              生成报告
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadAnalytics}
              loading={isLoading}
            >
              刷新
            </Button>
          </Space>
        }
      />

      {/* ---- Top metric cards ---- */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {metrics.map((metric, idx) => (
          <Col xs={12} sm={12} md={6} key={metric.label}>
            <Card
              size="small"
              style={{
                background: "#1f1f1f",
                borderColor: "#303030",
                borderTop: `2px solid ${metricIconColors[idx]}`,
              }}
            >
              <Statistic
                title={
                  <span style={{ color: "#8c8c8c", fontSize: 13 }}>{metric.label}</span>
                }
                value={metric.value}
                prefix={
                  <span style={{ color: metricIconColors[idx], marginRight: 4 }}>
                    {metric.icon}
                  </span>
                }
                valueStyle={{ fontSize: 28, fontWeight: 600, color: "#e8e8e8" }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}
      {reportMessage && (
        <Alert
          type="success"
          message={reportMessage}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin tip="正在加载数据洞察..." />
        </div>
      ) : (
        <>
          {/* ---- Main 2-column layout ---- */}
          <Row gutter={[16, 16]}>
            {/* Left column: Top Content table */}
            <Col xs={24} lg={16}>
              <Card
                title={
                  <Space>
                    <FireOutlined style={{ color: "#f5222d" }} />
                    <span>高潜内容</span>
                  </Space>
                }
                extra={<Link to="/platforms/xhs/library">进入内容库</Link>}
                style={{ background: "#1f1f1f", borderColor: "#303030", height: "100%" }}
                styles={{ body: { padding: "12px 16px" } }}
              >
                <Table<AnalyticsTopContent>
                  columns={topContentColumns}
                  dataSource={topContent}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 10, size: "small" }}
                  locale={{ emptyText: "暂无保存笔记。" }}
                />
              </Card>
            </Col>

            {/* Right column: Hot Topics + Comment Terms stacked */}
            <Col xs={24} lg={8}>
              <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%" }}>
                {/* Hot Topics with progress bars */}
                <Card
                  title={
                    <Space>
                      <TagsOutlined style={{ color: "#1668dc" }} />
                      <span>热点话题</span>
                    </Space>
                  }
                  extra={
                    <Tag color="blue">{hotTopics.length} 个</Tag>
                  }
                  style={{ background: "#1f1f1f", borderColor: "#303030", flex: 1 }}
                  styles={{ body: { padding: "8px 16px", maxHeight: 320, overflowY: "auto" } }}
                >
                  {hotTopics.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标签或话题数据。" />
                  ) : (
                    <List
                      dataSource={hotTopics}
                      split={false}
                      renderItem={(topic) => {
                        const pct = Math.round((topic.engagement / maxTopicEngagement) * 100);
                        return (
                          <List.Item style={{ padding: "8px 0", border: "none" }}>
                            <div style={{ width: "100%" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                                <Text style={{ color: "#e8e8e8", fontSize: 13 }}>#{topic.keyword}</Text>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {topic.notes} 篇 / {formatNumber(topic.engagement)} 互动
                                </Text>
                              </div>
                              <Progress
                                percent={pct}
                                showInfo={false}
                                strokeColor="#1668dc"
                                trailColor="#303030"
                                size="small"
                              />
                            </div>
                          </List.Item>
                        );
                      }}
                    />
                  )}
                </Card>

                {/* Comment Terms - Tag Cloud */}
                <Card
                  title={
                    <Space>
                      <CommentOutlined style={{ color: "#faad14" }} />
                      <span>评论关键词</span>
                    </Space>
                  }
                  extra={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {commentInsights.question_count} 个提问
                    </Text>
                  }
                  style={{ background: "#1f1f1f", borderColor: "#303030" }}
                  styles={{ body: { padding: "12px 16px" } }}
                >
                  {commentInsights.top_terms.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无评论数据。" />
                  ) : (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                      {commentInsights.top_terms.map((term, idx) => {
                        const fontSize = termSizes[Math.min(idx, termSizes.length - 1)];
                        const colors = ["#1668dc", "#13c2c2", "#52c41a", "#faad14", "#eb2f96", "#722ed1"];
                        const color = colors[idx % colors.length];
                        return (
                          <Tag
                            key={term.term}
                            color={color}
                            style={{
                              fontSize,
                              padding: "4px 10px",
                              lineHeight: 1.4,
                              border: "none",
                            }}
                          >
                            {term.term} x{term.count}
                          </Tag>
                        );
                      })}
                    </div>
                  )}
                </Card>
              </div>
            </Col>
          </Row>

          <Divider style={{ borderColor: "#303030", margin: "24px 0" }} />

          {/* ---- Bottom: Top Comments ---- */}
          <Card
            title={
              <Space>
                <CommentOutlined style={{ color: "#52c41a" }} />
                <span>高赞评论</span>
              </Space>
            }
            extra={
              <Tag>{commentInsights.top_comments.length} 条</Tag>
            }
            style={{ background: "#1f1f1f", borderColor: "#303030" }}
            styles={{ body: { padding: "8px 16px" } }}
          >
            <List
              dataSource={commentInsights.top_comments}
              locale={{ emptyText: "暂无已保存评论。" }}
              split={false}
              renderItem={(comment) => (
                <List.Item style={{ padding: "10px 0", borderBottom: "1px solid #262626" }}>
                  <List.Item.Meta
                    avatar={
                      <Avatar
                        size={36}
                        icon={<UserOutlined />}
                        style={{ backgroundColor: "#303030" }}
                      />
                    }
                    title={
                      <Text style={{ color: "#d9d9d9", fontSize: 13 }}>{comment.content}</Text>
                    }
                    description={
                      <Space size={16} style={{ marginTop: 2 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {comment.user_name || "未知用户"}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {comment.like_count} likes
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </>
      )}
    </div>
  );
}
