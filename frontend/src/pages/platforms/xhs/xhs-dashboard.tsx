import {
  DashboardOutlined,
  DatabaseOutlined,
  HeartOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Empty, List, Row, Statistic, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../../../components/layout/app-shell";
import { fetchXhsOverview } from "../../../lib/api";
import type { DashboardOverview } from "../../../types";

const { Text } = Typography;

const fallbackOverview: DashboardOverview = {
  platform: "xhs",
  today_crawls: 0,
  saved_notes: 0,
  pending_publishes: 0,
  healthy_accounts: 0,
  at_risk_accounts: 0,
  hot_topics: [],
  recent_activity: [],
};

export function XhsDashboard() {
  const [overview, setOverview] = useState<DashboardOverview>(fallbackOverview);

  useEffect(() => {
    fetchXhsOverview()
      .then(setOverview)
      .catch(() => setOverview(fallbackOverview));
  }, []);

  const metrics = [
    { label: "今日抓取", value: overview.today_crawls, icon: <DatabaseOutlined /> },
    { label: "内容库笔记", value: overview.saved_notes, icon: <HeartOutlined /> },
    { label: "待发布", value: overview.pending_publishes, icon: <ScheduleOutlined /> },
    { label: "健康账号", value: overview.healthy_accounts, icon: <SafetyCertificateOutlined /> },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="XHS Workspace"
        title="小红书运营总览"
        description="把抓取、洞察、AI 创作和发布任务放在同一张操作台上。"
        action={
          <Link to="/platforms/xhs/discovery">
            <Button type="primary" icon={<DashboardOutlined />}>
              开始发现
            </Button>
          </Link>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {metrics.map((metric) => (
          <Col xs={12} sm={12} md={6} key={metric.label}>
            <Card size="small" style={{ background: "#1f1f1f", borderColor: "#303030" }}>
              <Statistic
                title={metric.label}
                value={metric.value}
                prefix={metric.icon}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={16}>
          <Card
            title="高潜话题"
            extra={<Link to="/platforms/xhs/analytics">查看洞察</Link>}
            style={{ background: "#1f1f1f", borderColor: "#303030" }}
          >
            {overview.hot_topics.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无话题数据" />
            ) : (
              <List
                dataSource={overview.hot_topics}
                renderItem={(topic) => (
                  <List.Item
                    extra={<Text strong>{topic.engagement.toLocaleString()}</Text>}
                  >
                    <List.Item.Meta
                      title={topic.keyword}
                      description={`${topic.notes} 篇笔记`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card
            title="自动化结果"
            extra={<RobotOutlined />}
            style={{ background: "#1f1f1f", borderColor: "#303030" }}
          >
            {overview.recent_activity.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无最近活动" />
            ) : (
              <List
                dataSource={overview.recent_activity}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={item.title}
                      description={item.status}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
