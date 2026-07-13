import {
  ApiOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  UserOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  App,
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  theme,
} from "antd";
import type { TableColumnsType } from "antd";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { useAuth } from "../../hooks/use-auth";
import {
  fetchAdminContent,
  fetchAdminContentSummary,
  fetchAdminModelConfigs,
  fetchAdminOverview,
  fetchAdminPlatformAccounts,
  fetchAdminSystemHealth,
  fetchAdminTasks,
  fetchAdminUsers,
  updateAdminUser,
} from "../../lib/api";
import type { AdminListParams } from "../../lib/api";
import type {
  AdminAuditEvent,
  AdminContent,
  AdminContentSummary,
  AdminModelConfig,
  AdminOverview,
  AdminPlatformAccount,
  AdminServiceHealth,
  AdminSystemHealth,
  AdminTask,
  AdminUser,
  Paginated,
} from "../../types";

const { Text, Title } = Typography;

function formatTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function statusColor(status: string): string {
  const value = status.toLowerCase();
  if (["healthy", "active", "approved", "completed", "success", "succeeded", "published", "online"].includes(value)) return "success";
  if (["failed", "error", "down", "rejected", "inactive", "disabled", "expired"].includes(value)) return "error";
  if (["running", "queued", "pending", "pending_review", "flagged", "degraded", "risk", "warning"].includes(value)) return "warning";
  if (["cancelled", "paused"].includes(value)) return "default";
  return "blue";
}

function StatusTag({ status, label }: { status: string; label?: string }) {
  return <Tag color={statusColor(status)}>{label ?? status}</Tag>;
}

function AdminPageHeader({ title, description, loading, onRefresh }: { title: string; description: string; loading: boolean; onRefresh: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 18 }}>
      <div style={{ minWidth: 0 }}>
        <Title level={4} style={{ margin: 0 }}>{title}</Title>
        <Text type="secondary" style={{ fontSize: 13 }}>{description}</Text>
      </div>
      <Button icon={<ReloadOutlined />} loading={loading} onClick={onRefresh}>刷新</Button>
    </div>
  );
}

function FilterBar({ children, onSearch }: { children: ReactNode; onSearch: () => void }) {
  const { token } = theme.useToken();
  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, padding: 10, marginBottom: 12, background: token.colorBgContainer, border: `1px solid ${token.colorBorder}`, borderRadius: token.borderRadius }}>
      {children}
      <Button type="primary" icon={<SearchOutlined />} onClick={onSearch}>筛选</Button>
    </div>
  );
}

type CollectionLoader<T> = (params?: AdminListParams) => Promise<Paginated<T>>;

function useAdminCollection<T>(loader: CollectionLoader<T>) {
  const [data, setData] = useState<Paginated<T>>({ total: 0, page: 1, page_size: 20, items: [] });
  const [query, setQuery] = useState<AdminListParams>({ page: 1, page_size: 20 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (next?: AdminListParams) => {
    const request = next ?? query;
    setLoading(true);
    setError(null);
    try {
      const result = await loader(request);
      setData(result);
      setQuery(request);
    } catch {
      setError("数据加载失败，请检查服务状态后重试。");
    } finally {
      setLoading(false);
    }
  }, [loader, query]);

  useEffect(() => { void load({ page: 1, page_size: 20 }); }, []);

  return {
    data,
    query,
    loading,
    error,
    load,
    setQuery,
    replaceItem: (item: T, getId: (value: T) => number) => setData((current) => ({ ...current, items: current.items.map((value) => getId(value) === getId(item) ? item : value) })),
  };
}

function CollectionTable<T extends object>({
  state,
  columns,
  rowKey = "id",
  emptyText,
}: {
  state: ReturnType<typeof useAdminCollection<T>>;
  columns: TableColumnsType<T>;
  rowKey?: string;
  emptyText: string;
}) {
  return (
    <>
      {state.error && <Alert type="error" showIcon message={state.error} action={<Button size="small" onClick={() => void state.load()}>重试</Button>} style={{ marginBottom: 12 }} />}
      <Table<T>
        rowKey={rowKey}
        size="small"
        loading={state.loading}
        columns={columns}
        dataSource={state.data.items}
        scroll={{ x: 900 }}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} /> }}
        pagination={{
          current: state.data.page,
          pageSize: state.data.page_size,
          total: state.data.total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => void state.load({ ...state.query, page, page_size: pageSize }),
        }}
      />
    </>
  );
}

function OverviewPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setData(await fetchAdminOverview()); } catch { setError("管理概览加载失败。"); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const activityColumns: TableColumnsType<AdminAuditEvent> = [
    { title: "时间", dataIndex: "created_at", width: 170, render: formatTime },
    { title: "级别", dataIndex: "level", width: 90, render: (value) => <StatusTag status={value} /> },
    { title: "操作人", dataIndex: "actor", width: 130 },
    { title: "事件", dataIndex: "summary", ellipsis: true },
  ];
  const totalContent = data ? data.content.notes + data.content.drafts + data.content.generated_assets + data.content.publish_jobs : 0;

  return (
    <div>
      <AdminPageHeader title="管理总览" description="跨用户查看资源规模、运行风险和近期系统活动。" loading={loading} onRefresh={() => void load()} />
      {error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={() => void load()}>重试</Button>} />}
      {loading && !data ? <div style={{ padding: 80, textAlign: "center" }}><Spin tip="正在汇总系统数据..." /></div> : data && (
        <>
          <Row gutter={[12, 12]}>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="用户" value={data.users.total} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.users.active} 活跃</Text>} /></Card></Col>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="平台账号" value={data.platform_accounts.total} valueStyle={{ color: data.platform_accounts.at_risk ? "#faad14" : undefined }} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.platform_accounts.at_risk} 风险</Text>} /></Card></Col>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="内容资产" value={totalContent} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.content.drafts} 草稿</Text>} /></Card></Col>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="运行任务" value={data.tasks.running} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.tasks.queued} 排队</Text>} /></Card></Col>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="今日发布" value={data.publishes.published_today} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.publishes.failed_today} 失败</Text>} /></Card></Col>
            <Col xs={12} md={8} xl={4}><Card size="small"><Statistic title="模型配置" value={data.models.total} /></Card></Col>
          </Row>
          <div style={{ marginTop: 20 }}>
            <Space style={{ marginBottom: 8 }}><SafetyCertificateOutlined /><Text strong>近期系统活动</Text><Text type="secondary" style={{ fontSize: 12 }}>更新于 {formatTime(data.generated_at)}</Text></Space>
            <Table<AdminAuditEvent> rowKey="id" size="small" columns={activityColumns} dataSource={data.recent_activity ?? []} pagination={false} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无系统活动" /> }} />
          </div>
        </>
      )}
    </div>
  );
}

function UsersPage() {
  const auth = useAuth();
  const { message } = App.useApp();
  const state = useAdminCollection(fetchAdminUsers);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>();
  const [acting, setActing] = useState<number | null>(null);

  async function changeUser(user: AdminUser, patch: Partial<Pick<AdminUser, "is_active" | "is_admin">>) {
    setActing(user.id);
    try { state.replaceItem(await updateAdminUser(user.id, patch), (item) => item.id); message.success("用户权限已更新"); }
    catch { message.error("用户更新失败"); } finally { setActing(null); }
  }

  const columns: TableColumnsType<AdminUser> = [
    { title: "用户", dataIndex: "username", width: 180, render: (value) => <Space><UserOutlined /><Text strong>{value}</Text></Space> },
    { title: "角色", dataIndex: "is_admin", width: 100, render: (value) => value ? <Tag color="blue">管理员</Tag> : <Tag>用户</Tag> },
    { title: "状态", dataIndex: "is_active", width: 90, render: (value) => <StatusTag status={value ? "active" : "inactive"} label={value ? "启用" : "停用"} /> },
    { title: "账号 / 内容", width: 130, render: (_, record) => `${record.platform_account_count} / ${record.content_count}` },
    { title: "最近登录", dataIndex: "last_login_at", width: 170, render: formatTime },
    { title: "创建时间", dataIndex: "created_at", width: 170, render: formatTime },
    { title: "操作", fixed: "right", width: 190, render: (_, record) => <Space size={10}><Space size={4}><Text type="secondary" style={{ fontSize: 12 }}>启用</Text><Switch size="small" checked={record.is_active} loading={acting === record.id} disabled={record.id === auth.user?.id} onChange={(value) => void changeUser(record, { is_active: value })} /></Space><Space size={4}><Text type="secondary" style={{ fontSize: 12 }}>管理员</Text><Switch size="small" checked={record.is_admin} loading={acting === record.id} disabled={record.id === auth.user?.id} onChange={(value) => void changeUser(record, { is_admin: value })} /></Space></Space> },
  ];

  return <div><AdminPageHeader title="用户管理" description="管理后台访问权限和用户可用状态；当前管理员不能在此停用自己。" loading={state.loading} onRefresh={() => void state.load()} /><FilterBar onSearch={() => void state.load({ q: q || undefined, status, page: 1, page_size: state.query.page_size })}><Input value={q} onChange={(e) => setQ(e.target.value)} onPressEnter={() => void state.load({ q: q || undefined, status, page: 1, page_size: state.query.page_size })} allowClear placeholder="搜索用户名" prefix={<SearchOutlined />} style={{ width: 220, maxWidth: "100%" }} /><Select value={status} onChange={setStatus} allowClear placeholder="全部状态" style={{ width: 140, maxWidth: "100%" }} options={[{ value: "active", label: "已启用" }, { value: "inactive", label: "已停用" }, { value: "admin", label: "管理员" }]} /></FilterBar><CollectionTable state={state} columns={columns} emptyText="没有符合条件的用户" /></div>;
}

function PlatformAccountsPage() {
  const state = useAdminCollection(fetchAdminPlatformAccounts);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>();
  const [platform, setPlatform] = useState<string>();
  const columns: TableColumnsType<AdminPlatformAccount> = [
    { title: "平台账号", dataIndex: "nickname", width: 190, ellipsis: true, render: (value) => <Text strong>{value || "未命名账号"}</Text> },
    { title: "所属用户", dataIndex: "username", width: 150 },
    { title: "平台", dataIndex: "platform", width: 100, render: (value) => <Tag>{String(value).toUpperCase()}</Tag> },
    { title: "类型", dataIndex: "sub_type", width: 100, render: (value) => value || "-" },
    { title: "状态", dataIndex: "status", width: 110, render: (value) => <StatusTag status={value} /> },
    { title: "状态说明", dataIndex: "status_message", ellipsis: true },
    { title: "更新时间", dataIndex: "updated_at", width: 170, render: formatTime },
  ];
  const search = () => void state.load({ q: q || undefined, status, platform, page: 1, page_size: state.query.page_size });
  return <div><AdminPageHeader title="平台账号" description="查看所有用户绑定的平台身份和凭证健康状态。" loading={state.loading} onRefresh={() => void state.load()} /><FilterBar onSearch={search}><Input value={q} onChange={(e) => setQ(e.target.value)} onPressEnter={search} allowClear placeholder="昵称或所属用户" style={{ width: 220, maxWidth: "100%" }} /><Select value={platform} onChange={setPlatform} allowClear placeholder="全部平台" style={{ width: 130, maxWidth: "100%" }} options={[{ value: "xhs", label: "小红书" }, { value: "douyin", label: "抖音" }, { value: "kuaishou", label: "快手" }]} /><Select value={status} onChange={setStatus} allowClear placeholder="全部状态" style={{ width: 140, maxWidth: "100%" }} options={["active", "expired", "error", "healthy", "risk", "unknown"].map((value) => ({ value, label: value }))} /></FilterBar><CollectionTable state={state} columns={columns} emptyText="没有符合条件的平台账号" /></div>;
}

function ContentPage() {
  const state = useAdminCollection(fetchAdminContent);
  const [summary, setSummary] = useState<AdminContentSummary | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>();
  const [type, setType] = useState<string>();
  const loadSummary = useCallback(async () => { setSummaryError(false); try { setSummary(await fetchAdminContentSummary()); } catch { setSummary(null); setSummaryError(true); } }, []);
  useEffect(() => { void loadSummary(); }, [loadSummary]);
  const columns: TableColumnsType<AdminContent> = [
    { title: "内容", dataIndex: "title", ellipsis: true, render: (value) => <Text strong>{value || "无标题"}</Text> },
    { title: "所属用户", dataIndex: "username", width: 140 },
    { title: "平台", dataIndex: "platform", width: 90, render: (value) => value ? <Tag>{String(value).toUpperCase()}</Tag> : "-" },
    { title: "类型", dataIndex: "content_type", width: 100 },
    { title: "业务状态", dataIndex: "status", width: 120, render: (value) => value ? <StatusTag status={value} /> : "-" },
    { title: "创建时间", dataIndex: "created_at", width: 170, render: formatTime },
  ];
  const search = () => void state.load({ q: q || undefined, status, type, page: 1, page_size: state.query.page_size });
  return <div><AdminPageHeader title="内容治理" description="只读查看全站笔记、草稿、生成资产与发布记录。" loading={state.loading} onRefresh={() => { void state.load(); void loadSummary(); }} />{summaryError && <Alert type="warning" showIcon message="内容汇总加载失败" action={<Button size="small" onClick={() => void loadSummary()}>重试</Button>} style={{ marginBottom: 12 }} />}{summary && <Row gutter={[12, 12]} style={{ marginBottom: 14 }}><Col xs={12} lg={6}><Card size="small"><Statistic title="笔记" value={summary.notes} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="草稿" value={summary.drafts} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="生成资产" value={summary.generated_assets} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="发布任务" value={summary.publish_jobs} /></Card></Col></Row>}<FilterBar onSearch={search}><Input value={q} onChange={(e) => setQ(e.target.value)} onPressEnter={search} allowClear placeholder="标题或用户名" style={{ width: 220, maxWidth: "100%" }} /><Select value={status} onChange={setStatus} allowClear placeholder="全部业务状态" style={{ width: 150, maxWidth: "100%" }} options={["saved", "draft", "generated", "pending", "scheduled", "publishing", "published", "failed", "cancelled"].map((value) => ({ value, label: value }))} /><Select value={type} onChange={setType} allowClear placeholder="全部内容类型" style={{ width: 150, maxWidth: "100%" }} options={["note", "draft", "generated_asset", "publish_job"].map((value) => ({ value, label: value }))} /></FilterBar><CollectionTable state={state} columns={columns} rowKey="resource_key" emptyText="没有符合条件的内容" /></div>;
}

function TasksPage() {
  const state = useAdminCollection(fetchAdminTasks);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>();
  const [type, setType] = useState<string>();
  const columns: TableColumnsType<AdminTask> = [
    { title: "任务", dataIndex: "id", width: 180, render: (value, record) => <div><Text strong ellipsis style={{ display: "block" }}>{record.title || `#${value}`}</Text><Text type="secondary" style={{ fontSize: 11 }}>#{value} · {record.task_type}</Text></div> },
    { title: "用户", dataIndex: "username", width: 130 },
    { title: "状态", dataIndex: "status", width: 110, render: (value) => <StatusTag status={value} /> },
    { title: "进度", dataIndex: "progress", width: 150, render: (value) => typeof value === "number" ? <Progress percent={Math.round(value)} size="small" status={value >= 100 ? "success" : "active"} /> : "-" },
    { title: "错误类型", dataIndex: "error_type", width: 130, render: (value) => value || "-" },
    { title: "重试", dataIndex: "retry_count", width: 80, render: (value, record) => `${value} / ${record.max_retries}` },
    { title: "创建时间", dataIndex: "created_at", width: 170, render: formatTime },
    { title: "开始时间", dataIndex: "started_at", width: 170, render: formatTime },
    { title: "结束时间", dataIndex: "finished_at", width: 170, render: formatTime },
  ];
  const search = () => void state.load({ q: q || undefined, status, type, page: 1, page_size: state.query.page_size });
  return <div><AdminPageHeader title="任务中心" description="只读观察后台任务生命周期、进度、重试次数及失败分类。" loading={state.loading} onRefresh={() => void state.load()} /><FilterBar onSearch={search}><Input value={q} onChange={(e) => setQ(e.target.value)} onPressEnter={search} allowClear placeholder="任务编号、类型或用户名" style={{ width: 220, maxWidth: "100%" }} /><Select value={status} onChange={setStatus} allowClear placeholder="全部状态" style={{ width: 140, maxWidth: "100%" }} options={[{ value: "pending", label: "排队" }, { value: "running", label: "运行中" }, { value: "completed", label: "已完成" }, { value: "failed", label: "失败" }, { value: "exhausted", label: "重试耗尽" }, { value: "cancelled", label: "已取消" }]} /><Select value={type} onChange={setType} allowClear placeholder="全部类型" style={{ width: 150, maxWidth: "100%" }} options={[{ value: "crawl", label: "采集" }, { value: "ai", label: "AI" }, { value: "publish", label: "发布" }, { value: "auto_ops", label: "自动运营" }, { value: "monitoring", label: "监控" }]} /></FilterBar><CollectionTable state={state} columns={columns} emptyText="没有符合条件的任务" /></div>;
}

function ModelConfigsPage() {
  const state = useAdminCollection(fetchAdminModelConfigs);
  const [q, setQ] = useState("");
  const [type, setType] = useState<string>();
  const columns: TableColumnsType<AdminModelConfig> = [
    { title: "配置", dataIndex: "name", ellipsis: true, render: (value, record) => <Space><RobotOutlined /><div><Text strong>{value}</Text><br /><Text type="secondary" style={{ fontSize: 11 }}>{record.model_name}</Text></div></Space> },
    { title: "用户", dataIndex: "username", width: 130 },
    { title: "类型", dataIndex: "model_type", width: 90, render: (value) => <Tag>{value}</Tag> },
    { title: "Provider", dataIndex: "provider", width: 150, ellipsis: true },
    { title: "Base URL", dataIndex: "base_url", width: 220, ellipsis: true },
    { title: "默认", dataIndex: "is_default", width: 80, render: (value) => value ? <Tag color="blue">默认</Tag> : "-" },
  ];
  const search = () => void state.load({ q: q || undefined, type, page: 1, page_size: state.query.page_size });
  return <div><AdminPageHeader title="模型配置" description="只读查看全站模型路由；管理端不返回或展示任何 API Key 信息。" loading={state.loading} onRefresh={() => void state.load()} /><FilterBar onSearch={search}><Input value={q} onChange={(e) => setQ(e.target.value)} onPressEnter={search} allowClear placeholder="配置、模型或用户名" style={{ width: 230, maxWidth: "100%" }} /><Select value={type} onChange={setType} allowClear placeholder="全部模型类型" style={{ width: 150, maxWidth: "100%" }} options={[{ value: "text", label: "文本模型" }, { value: "image", label: "图片模型" }]} /></FilterBar><CollectionTable state={state} columns={columns} emptyText="没有符合条件的模型配置" /></div>;
}

function SystemHealthPage() {
  const [data, setData] = useState<AdminSystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setData(await fetchAdminSystemHealth()); } catch { setError("系统状态加载失败。"); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  const columns: TableColumnsType<AdminServiceHealth> = [
    { title: "服务", dataIndex: "name", render: (value) => <Space><ApiOutlined /><Text strong>{value}</Text></Space> },
    { title: "状态", dataIndex: "status", width: 120, render: (value) => <StatusTag status={value} /> },
    { title: "延迟", dataIndex: "latency_ms", width: 120, render: (value) => typeof value === "number" ? `${value} ms` : "-" },
    { title: "说明", dataIndex: "message", ellipsis: true, render: (value) => value || "-" },
  ];
  const uptime = data ? `${Math.floor(data.uptime_seconds / 86400)} 天 ${Math.floor((data.uptime_seconds % 86400) / 3600)} 小时` : "-";
  return <div><AdminPageHeader title="系统状态" description="查看 API、数据库、队列和外部依赖的即时健康信息。" loading={loading} onRefresh={() => void load()} />{error && <Alert type="error" showIcon message={error} action={<Button size="small" onClick={() => void load()}>重试</Button>} />}{loading && !data ? <div style={{ padding: 80, textAlign: "center" }}><Spin tip="正在检查系统服务..." /></div> : data && <><Alert type={data.status === "healthy" ? "success" : data.status === "degraded" ? "warning" : "error"} showIcon icon={data.status === "healthy" ? <CheckCircleOutlined /> : <WarningOutlined />} message={`系统状态：${data.status}`} description={`检查时间 ${formatTime(data.checked_at)}`} style={{ marginBottom: 14 }} /><Row gutter={[12, 12]} style={{ marginBottom: 18 }}><Col xs={12} lg={6}><Card size="small"><Statistic title="版本" value={data.version || "-"} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="运行时长" value={uptime} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="数据库延迟" value={data.database.latency_ms ?? 0} suffix="ms" prefix={data.database.status === "healthy" ? <CheckCircleOutlined /> : <WarningOutlined />} /></Card></Col><Col xs={12} lg={6}><Card size="small"><Statistic title="队列积压" value={data.queue.pending} suffix={<Text type="secondary" style={{ fontSize: 12 }}>{data.queue.running} 运行</Text>} /></Card></Col></Row><Space style={{ marginBottom: 8 }}><ApiOutlined /><Text strong>服务明细</Text></Space><Table<AdminServiceHealth> rowKey="name" size="small" columns={columns} dataSource={data.services} pagination={false} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无服务检查项" /> }} /></>}</div>;
}

export function AdminSectionPage() {
  const { section } = useParams();
  if (section === "overview") return <OverviewPage />;
  if (section === "users") return <UsersPage />;
  if (section === "platform-accounts") return <PlatformAccountsPage />;
  if (section === "content") return <ContentPage />;
  if (section === "tasks") return <TasksPage />;
  if (section === "model-configs") return <ModelConfigsPage />;
  if (section === "system-health") return <SystemHealthPage />;
  return <Navigate to="/admin/overview" replace />;
}
