import {
  ClockCircleOutlined,
  DeleteOutlined,
  DownOutlined,
  LinkOutlined,
  ReloadOutlined,
  RightOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  createMonitoringTarget,
  deleteMonitoringTarget,
  fetchMonitoringTargets,
  refreshMonitoringTarget,
  fetchMonitoringSnapshots,
} from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { MonitoringTarget, MonitoringSnapshot } from "../../../types";

const { Text } = Typography;

const cardStyle: React.CSSProperties = {
  background: "#1f1f1f",
  borderColor: "#303030",
};

function extractEngagement(snapshot: MonitoringSnapshot | undefined): {
  likes: number;
  collects: number;
  comments: number;
  shares: number;
} {
  const defaults = { likes: 0, collects: 0, comments: 0, shares: 0 };
  if (!snapshot) return defaults;
  const p = snapshot.payload as Record<string, unknown> | undefined;
  if (!p) return defaults;
  return {
    likes: typeof p.likes === "number" ? p.likes : 0,
    collects: typeof p.collects === "number" ? p.collects : 0,
    comments: typeof p.comments === "number" ? p.comments : 0,
    shares: typeof p.shares === "number" ? p.shares : 0,
  };
}

function getRefreshInterval(target: MonitoringTarget): number {
  const cfg = target.config as Record<string, unknown> | undefined;
  if (cfg && typeof cfg.refresh_interval_minutes === "number") {
    return cfg.refresh_interval_minutes;
  }
  return 30;
}

export function XhsBenchmarksPage() {
  const [targets, setTargets] = useState<MonitoringTarget[]>([]);
  const [snapshots, setSnapshots] = useState<Record<number, MonitoringSnapshot[]>>({});
  const [expandedTargetId, setExpandedTargetId] = useState<number | null>(null);
  const [newUrl, setNewUrl] = useState("");
  const [newInterval, setNewInterval] = useState<number>(30);
  const [isAdding, setIsAdding] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshingIds, setRefreshingIds] = useState<Set<number>>(new Set());
  const [loadingSnapshotIds, setLoadingSnapshotIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [latestSnapshots, setLatestSnapshots] = useState<Record<number, MonitoringSnapshot>>({});

  const loadTargets = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchMonitoringTargets();
      const noteUrlTargets = result.items.filter(
        (t) => t.target_type === "note_url"
      );
      setTargets(noteUrlTargets);

      // Load latest snapshot for each target
      const snapshotEntries: Record<number, MonitoringSnapshot> = {};
      await Promise.allSettled(
        noteUrlTargets.map(async (t) => {
          try {
            const snap = await fetchMonitoringSnapshots(t.id);
            if (snap.items.length > 0) {
              snapshotEntries[t.id] = snap.items[0];
            }
          } catch {
            // ignore individual snapshot failures
          }
        })
      );
      setLatestSnapshots(snapshotEntries);
    } catch {
      setError("竞品数据加载失败。");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTargets();
  }, [loadTargets]);

  async function handleAdd() {
    const trimmed = newUrl.trim();
    if (!trimmed) return;
    setIsAdding(true);
    setError(null);
    setMessage(null);
    try {
      await createMonitoringTarget({
        target_type: "note_url",
        name: trimmed,
        value: trimmed,
        config: { refresh_interval_minutes: newInterval },
      });
      setNewUrl("");
      setNewInterval(30);
      setMessage("已添加监控目标。");
      await loadTargets();
    } catch {
      setError("添加监控目标失败。");
    } finally {
      setIsAdding(false);
    }
  }

  async function handleRefresh(targetId: number) {
    setRefreshingIds((prev) => new Set(prev).add(targetId));
    setError(null);
    try {
      const result = await refreshMonitoringTarget(targetId);
      // Update the target in state
      setTargets((prev) =>
        prev.map((t) => (t.id === targetId ? result.target : t))
      );
      // Update the latest snapshot
      if (result.snapshot) {
        setLatestSnapshots((prev) => ({ ...prev, [targetId]: result.snapshot }));
      }
      setMessage("刷新成功。");
    } catch {
      setError("刷新失败，请稍后重试。");
    } finally {
      setRefreshingIds((prev) => {
        const next = new Set(prev);
        next.delete(targetId);
        return next;
      });
    }
  }

  async function handleDelete(targetId: number) {
    setError(null);
    try {
      await deleteMonitoringTarget(targetId);
      setTargets((prev) => prev.filter((t) => t.id !== targetId));
      setLatestSnapshots((prev) => {
        const next = { ...prev };
        delete next[targetId];
        return next;
      });
      setSnapshots((prev) => {
        const next = { ...prev };
        delete next[targetId];
        return next;
      });
      if (expandedTargetId === targetId) {
        setExpandedTargetId(null);
      }
      setMessage("已删除监控目标。");
    } catch {
      setError("删除失败。");
    }
  }

  async function handleToggleExpand(targetId: number) {
    if (expandedTargetId === targetId) {
      setExpandedTargetId(null);
      return;
    }
    setExpandedTargetId(targetId);
    if (!snapshots[targetId]) {
      setLoadingSnapshotIds((prev) => new Set(prev).add(targetId));
      try {
        const result = await fetchMonitoringSnapshots(targetId);
        setSnapshots((prev) => ({ ...prev, [targetId]: result.items }));
      } catch {
        setSnapshots((prev) => ({ ...prev, [targetId]: [] }));
      } finally {
        setLoadingSnapshotIds((prev) => {
          const next = new Set(prev);
          next.delete(targetId);
          return next;
        });
      }
    }
  }

  const snapshotColumns = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (v: string) => formatShanghaiTime(v),
    },
    {
      title: "赞",
      key: "likes",
      width: 80,
      render: (_: unknown, record: MonitoringSnapshot) =>
        extractEngagement(record).likes,
    },
    {
      title: "藏",
      key: "collects",
      width: 80,
      render: (_: unknown, record: MonitoringSnapshot) =>
        extractEngagement(record).collects,
    },
    {
      title: "评",
      key: "comments",
      width: 80,
      render: (_: unknown, record: MonitoringSnapshot) =>
        extractEngagement(record).comments,
    },
    {
      title: "转",
      key: "shares",
      width: 80,
      render: (_: unknown, record: MonitoringSnapshot) =>
        extractEngagement(record).shares,
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Competitive Analysis"
        title="竞品分析"
        description="导入笔记链接追踪互动数据变化，洞察竞品内容表现。"
        action={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadTargets}
            loading={isLoading}
          >
            刷新
          </Button>
        }
      />

      {/* Add Target Section */}
      <Card size="small" style={{ ...cardStyle, marginBottom: 24 }}>
        <Space wrap style={{ width: "100%" }}>
          <Input
            placeholder="粘贴小红书笔记链接"
            prefix={<LinkOutlined />}
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            onPressEnter={handleAdd}
            style={{ width: 400 }}
            allowClear
          />
          <Space>
            <Text type="secondary">刷新间隔：</Text>
            <InputNumber
              min={10}
              max={1440}
              value={newInterval}
              onChange={(v) => setNewInterval(v ?? 30)}
              addonAfter="分钟"
              style={{ width: 140 }}
            />
          </Space>
          <Button type="primary" onClick={handleAdd} loading={isAdding}>
            添加
          </Button>
        </Space>
      </Card>

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: 16 }}
        />
      )}
      {message && (
        <Alert
          type="success"
          message={message}
          showIcon
          closable
          onClose={() => setMessage(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin tip="正在加载竞品数据..." />
        </div>
      ) : targets.length === 0 ? (
        <Card style={cardStyle}>
          <Empty description="暂无竞品目标，在上方输入笔记链接添加监控。" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {targets.map((target) => {
            const eng = extractEngagement(latestSnapshots[target.id]);
            const interval = getRefreshInterval(target);
            const isExpanded = expandedTargetId === target.id;
            const isRefreshing = refreshingIds.has(target.id);
            const isLoadingSnapshots = loadingSnapshotIds.has(target.id);

            return (
              <Col xs={24} lg={12} key={target.id}>
                <Card
                  style={cardStyle}
                  styles={{ body: { padding: 16 } }}
                  hoverable
                >
                  {/* Header row */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
                      <Text
                        strong
                        style={{ display: "block", marginBottom: 4 }}
                        ellipsis={{ tooltip: target.value }}
                      >
                        {target.name || target.value}
                      </Text>
                      <Text
                        type="secondary"
                        style={{ fontSize: 12 }}
                        ellipsis={{ tooltip: target.value }}
                      >
                        {target.value}
                      </Text>
                    </div>
                    <Tag
                      color={target.status === "active" ? "green" : "default"}
                    >
                      {target.status === "active" ? "监控中" : "已暂停"}
                    </Tag>
                  </div>

                  {/* Meta info */}
                  <Space
                    size="middle"
                    style={{ marginBottom: 12, flexWrap: "wrap" }}
                  >
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      每 {interval} 分钟
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      最近刷新：{formatShanghaiTime(target.last_refreshed_at)}
                    </Text>
                  </Space>

                  {/* Engagement metrics */}
                  <div
                    style={{
                      display: "flex",
                      gap: 16,
                      marginBottom: 12,
                      padding: "8px 12px",
                      background: "#141414",
                      borderRadius: 6,
                    }}
                  >
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        赞
                      </Text>
                      <div style={{ fontWeight: 600, fontSize: 16 }}>
                        {eng.likes.toLocaleString()}
                      </div>
                    </div>
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        藏
                      </Text>
                      <div style={{ fontWeight: 600, fontSize: 16 }}>
                        {eng.collects.toLocaleString()}
                      </div>
                    </div>
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        评
                      </Text>
                      <div style={{ fontWeight: 600, fontSize: 16 }}>
                        {eng.comments.toLocaleString()}
                      </div>
                    </div>
                    <div style={{ textAlign: "center", flex: 1 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        转
                      </Text>
                      <div style={{ fontWeight: 600, fontSize: 16 }}>
                        {eng.shares.toLocaleString()}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <Space>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={isRefreshing}
                      onClick={() => handleRefresh(target.id)}
                    >
                      刷新
                    </Button>
                    <Popconfirm
                      title="确认删除此监控目标？"
                      onConfirm={() => handleDelete(target.id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                      >
                        删除
                      </Button>
                    </Popconfirm>
                    <Button
                      size="small"
                      type="text"
                      icon={
                        isExpanded ? <DownOutlined /> : <RightOutlined />
                      }
                      onClick={() => handleToggleExpand(target.id)}
                    >
                      历史快照
                    </Button>
                  </Space>

                  {/* Expandable snapshot history */}
                  {isExpanded && (
                    <div style={{ marginTop: 16 }}>
                      {isLoadingSnapshots ? (
                        <div style={{ textAlign: "center", padding: 24 }}>
                          <Spin size="small" />
                        </div>
                      ) : !snapshots[target.id] ||
                        snapshots[target.id].length === 0 ? (
                        <Empty
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="暂无快照数据"
                        />
                      ) : (
                        <Table
                          dataSource={snapshots[target.id]}
                          columns={snapshotColumns}
                          rowKey="id"
                          size="small"
                          pagination={false}
                          scroll={{ y: 240 }}
                          style={{ background: "transparent" }}
                        />
                      )}
                    </div>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );
}
