import {
  AimOutlined,
  BarChartOutlined,
  BellOutlined,
  CloudDownloadOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  KeyOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  SearchOutlined,
  SendOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  StarOutlined,
  SunOutlined,
  UserOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons";
import {
  Avatar,
  Badge,
  Button,
  Col,
  Dropdown,
  Layout,
  List,
  Menu,
  Row,
  Space,
  Tag,
  Typography,
} from "antd";
import type { MenuProps } from "antd";
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import KeepAliveRouteOutlet from "keepalive-for-react-router";

import { useAuth } from "../../hooks/use-auth";
import { useThemeMode } from "../../app/providers";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "../../lib/api";
import type { AppNotification } from "../../types";

const { Sider, Header, Content } = Layout;
const { Title, Text } = Typography;

const mainNavItems: MenuProps["items"] = [
  { key: "/platforms/xhs/dashboard", icon: <DashboardOutlined />, label: "总览" },
  { key: "/platforms/xhs/accounts", icon: <SafetyCertificateOutlined />, label: "账号矩阵" },
  { key: "/platforms/xhs/discovery", icon: <SearchOutlined />, label: "笔记发现" },
  { key: "/platforms/xhs/crawler", icon: <CloudDownloadOutlined />, label: "数据抓取" },
  { key: "/platforms/xhs/keywords", icon: <KeyOutlined />, label: "关键词组" },
  { key: "/platforms/xhs/analytics", icon: <BarChartOutlined />, label: "数据洞察" },
  { key: "/platforms/xhs/benchmarks", icon: <AimOutlined />, label: "竞品监控" },
  { key: "/platforms/xhs/image-studio", icon: <StarOutlined />, label: "图片工坊" },
  { key: "/platforms/xhs/video-studio", icon: <VideoCameraOutlined />, label: "视频工坊" },
  { key: "/platforms/xhs/library", icon: <DatabaseOutlined />, label: "内容库" },
  { key: "/platforms/xhs/drafts", icon: <FileTextOutlined />, label: "草稿工坊" },
  { key: "/platforms/xhs/publish", icon: <SendOutlined />, label: "发布中心" },
  { key: "/platforms/xhs/auto-ops", icon: <ThunderboltOutlined />, label: "自动运营" },
];

const footerNavItems: MenuProps["items"] = [
  { key: "/tasks", icon: <ScheduleOutlined />, label: "任务中心" },
  { key: "/models", icon: <RobotOutlined />, label: "模型配置" },
  { key: "/settings", icon: <SettingOutlined />, label: "设置" },
];

function levelColor(level: string): string {
  if (level === "error") return "#ef4444";
  if (level === "warning") return "#eab308";
  return "#666";
}

export function AppShell() {
  const auth = useAuth();
  const { mode: themeMode, toggle: toggleTheme } = useThemeMode();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const loadNotifications = useCallback(async () => {
    try {
      const res = await fetchNotifications({ page_size: 20 });
      setNotifications(res.items);
      setUnreadCount(res.items.filter((n) => !n.read).length);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    void loadNotifications();
    const timer = setInterval(() => void loadNotifications(), 30_000);
    return () => clearInterval(timer);
  }, [loadNotifications]);

  const handleMarkRead = async (id: number) => { await markNotificationRead(id); void loadNotifications(); };
  const handleMarkAllRead = async () => { await markAllNotificationsRead(); void loadNotifications(); };
  const handleMenuClick: MenuProps["onClick"] = ({ key }) => { navigate(key); };
  const selectedKeys = [location.pathname];

  const notificationDropdownContent = (
    <div style={{ width: 360, background: "#1f1f1f", borderRadius: 8, border: "1px solid #303030", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid #303030" }}>
        <Text strong style={{ fontSize: 14 }}>通知</Text>
        {unreadCount > 0 && <Button type="link" size="small" onClick={() => void handleMarkAllRead()}>全部已读</Button>}
      </div>
      <div style={{ maxHeight: 400, overflowY: "auto" }}>
        {notifications.length === 0 ? (
          <div style={{ padding: "32px 16px", textAlign: "center", color: "rgba(255,255,255,0.35)" }}>暂无通知</div>
        ) : (
          <List
            dataSource={notifications}
            renderItem={(n) => (
              <List.Item key={n.id} style={{ padding: "10px 16px", cursor: n.read ? "default" : "pointer", background: n.read ? "transparent" : "rgba(22,104,220,0.06)", borderBottom: "1px solid #262626" }} onClick={() => !n.read && void handleMarkRead(n.id)}>
                <List.Item.Meta
                  avatar={<span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: levelColor(n.level), marginTop: 6 }} />}
                  title={<Text style={{ fontSize: 13 }}>{n.title}</Text>}
                  description={<div>{n.body && <Text type="secondary" style={{ fontSize: 12, display: "block" }}>{n.body}</Text>}<Text type="secondary" style={{ fontSize: 11 }}>{new Date(n.created_at).toLocaleString("zh-CN")}</Text></div>}
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );

  const siderWidth = collapsed ? 64 : 220;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsed={collapsed}
        width={220}
        collapsedWidth={64}
        theme="dark"
        trigger={null}
        style={{
          height: "100vh",
          position: "fixed",
          left: 0,
          top: 0,
          bottom: 0,
          borderRight: "1px solid #303030",
          overflow: "hidden",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Logo */}
          <div
            style={{ padding: collapsed ? "14px 0" : "14px 16px", display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "space-between", borderBottom: "1px solid #303030", flexShrink: 0, cursor: "pointer" }}
            onClick={() => navigate("/platform-select")}
          >
            <Space align="center" size={collapsed ? 0 : 8}>
              <img src="/logo.jpg" alt="Logo" style={{ width: 28, height: 28, borderRadius: 6, objectFit: "cover", flexShrink: 0 }} />
              {!collapsed && <span style={{ fontWeight: 600, fontSize: 14, color: "rgba(255,255,255,.85)" }}>Spider XHS</span>}
            </Space>
            {!collapsed && <Button type="text" size="small" icon={<MenuFoldOutlined />} onClick={(e) => { e.stopPropagation(); setCollapsed(true); }} style={{ color: "rgba(255,255,255,.35)" }} />}
          </div>
          {collapsed && (
            <div style={{ textAlign: "center", padding: "6px 0", borderBottom: "1px solid #262626", flexShrink: 0 }}>
              <Button type="text" size="small" icon={<MenuUnfoldOutlined />} onClick={() => setCollapsed(false)} style={{ color: "rgba(255,255,255,.35)" }} />
            </div>
          )}

          {/* Main nav — scrollable */}
          <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
            <Menu theme="dark" mode="inline" selectedKeys={selectedKeys} onClick={handleMenuClick} items={mainNavItems} style={{ borderRight: 0 }} />
          </div>

          {/* Footer — pinned to bottom */}
          <div style={{ flexShrink: 0, borderTop: "1px solid #303030" }}>
            <Menu theme="dark" mode="inline" selectedKeys={selectedKeys} onClick={handleMenuClick} items={footerNavItems} style={{ borderRight: 0 }} />
            <div style={{ padding: collapsed ? "8px 0" : "8px 16px", borderTop: "1px solid #262626", display: "flex", alignItems: "center", gap: 8, justifyContent: collapsed ? "center" : "flex-start" }}>
              <Avatar size={22} icon={<UserOutlined />} style={{ background: "#1668dc", flexShrink: 0, fontSize: 11 }}>{(auth.user?.username ?? "U")[0].toUpperCase()}</Avatar>
              {!collapsed && (
                <>
                  <Text type="secondary" ellipsis style={{ fontSize: 12, flex: 1, lineHeight: "22px" }}>{auth.user?.username ?? "用户"}</Text>
                  <Button type="text" icon={<LogoutOutlined />} onClick={() => void auth.logout()} size="small" style={{ color: "rgba(255,255,255,0.35)", flexShrink: 0 }} />
                </>
              )}
            </div>
          </div>
        </div>
      </Sider>

      <Layout style={{ marginLeft: siderWidth, transition: "margin-left 0.2s" }}>
        <Header style={{ padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "flex-end", borderBottom: "1px solid #303030", height: 48, lineHeight: "48px" }}>
          <Space size={12} align="center">
            <Button
              type="text"
              icon={themeMode === "dark" ? <SunOutlined style={{ fontSize: 16 }} /> : <MoonOutlined style={{ fontSize: 16 }} />}
              onClick={toggleTheme}
              title={themeMode === "dark" ? "切换为浅色模式" : "切换为暗色模式"}
              style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
            />
            <Dropdown dropdownRender={() => notificationDropdownContent} trigger={["click"]} placement="bottomRight">
              <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                <Button type="text" icon={<BellOutlined style={{ fontSize: 16 }} />} style={{ display: "flex", alignItems: "center", justifyContent: "center" }} />
              </Badge>
            </Dropdown>
            <Avatar size={28} style={{ background: "#1668dc", fontSize: 12, cursor: "default" }}>{(auth.user?.username ?? "U")[0].toUpperCase()}</Avatar>
          </Space>
        </Header>
        <Content style={{ padding: 24, minHeight: "calc(100vh - 48px)", overflow: "auto" }}>
          <KeepAliveRouteOutlet include={[/\/platforms\/xhs\/discovery/, /\/platforms\/xhs\/crawler/]} />
        </Content>
      </Layout>
    </Layout>
  );
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return (
    <Row justify="space-between" align="top" style={{ marginBottom: 24 }}>
      <Col>
        <Text type="secondary" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>{eyebrow}</Text>
        <Title level={3} style={{ margin: "4px 0 4px" }}>{title}</Title>
        <Text type="secondary">{description}</Text>
      </Col>
      {action && <Col>{action}</Col>}
    </Row>
  );
}
