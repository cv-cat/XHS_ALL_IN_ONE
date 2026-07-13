import {
  AppstoreOutlined,
  ApiOutlined,
  ControlOutlined,
  DatabaseOutlined,
  FileProtectOutlined,
  HomeOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  ScheduleOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Grid, Layout, Menu, Space, Tag, Typography, theme } from "antd";
import type { MenuProps } from "antd";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { useThemeMode } from "../../app/providers";
import { useAuth } from "../../hooks/use-auth";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const adminNavItems: MenuProps["items"] = [
  { key: "/admin/overview", icon: <AppstoreOutlined />, label: "总览" },
  { key: "/admin/users", icon: <TeamOutlined />, label: "用户" },
  { key: "/admin/platform-accounts", icon: <UserOutlined />, label: "平台账号" },
  { key: "/admin/content", icon: <FileProtectOutlined />, label: "内容治理" },
  { key: "/admin/tasks", icon: <ScheduleOutlined />, label: "任务中心" },
  { key: "/admin/model-configs", icon: <RobotOutlined />, label: "模型配置" },
  { key: "/admin/system-health", icon: <ApiOutlined />, label: "系统状态" },
];

export function AdminShell() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { mode: themeMode } = useThemeMode();
  const { token } = theme.useToken();
  const screens = Grid.useBreakpoint();
  const [collapsed, setCollapsed] = useState(false);
  const compactHeader = !screens.md;

  const selectedKey = adminNavItems
    ?.map((item) => String(item?.key ?? ""))
    .find((key) => location.pathname.startsWith(key)) ?? "/admin/overview";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={208}
        collapsedWidth={64}
        collapsed={collapsed}
        theme={themeMode}
        trigger={null}
        breakpoint="lg"
        onBreakpoint={(broken) => setCollapsed(broken)}
        style={{ position: "fixed", inset: "0 auto 0 0", zIndex: 20, borderRight: `1px solid ${token.colorBorder}` }}
      >
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <div
            style={{ height: 49, padding: collapsed ? "0" : "0 14px", display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "space-between", borderBottom: `1px solid ${token.colorBorder}` }}
          >
            <Space size={8}>
              <ControlOutlined style={{ color: token.colorPrimary, fontSize: 18 }} />
              {!collapsed && <Text strong>运营管理</Text>}
            </Space>
            {!collapsed && <Tag color="blue" style={{ marginInlineEnd: 0 }}>ADMIN</Tag>}
          </div>

          <Menu
            theme={themeMode}
            mode="inline"
            selectedKeys={[selectedKey]}
            items={adminNavItems}
            onClick={({ key }) => navigate(key)}
            style={{ flex: 1, paddingTop: 8, borderInlineEnd: 0 }}
          />

          <div style={{ borderTop: `1px solid ${token.colorBorder}`, padding: 8 }}>
            <Button type="text" block icon={<HomeOutlined />} onClick={() => navigate("/platform-select")}>
              {!collapsed && "返回工作台"}
            </Button>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 4px 0" }}>
              <Avatar size={24} style={{ background: token.colorPrimary }}>{(auth.user?.username ?? "A")[0].toUpperCase()}</Avatar>
              {!collapsed && <Text ellipsis style={{ flex: 1, fontSize: 12 }}>{auth.user?.username}</Text>}
              {!collapsed && <Button type="text" size="small" title="退出登录" icon={<LogoutOutlined />} onClick={() => void auth.logout()} />}
            </div>
          </div>
        </div>
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 64 : 208, transition: "margin-left 0.2s" }}>
        <Header style={{ height: 49, padding: compactHeader ? "0 10px" : "0 20px", display: "flex", alignItems: "center", gap: compactHeader ? 6 : 12, borderBottom: `1px solid ${token.colorBorder}`, position: "sticky", top: 0, zIndex: 10, minWidth: 0, overflow: "hidden" }}>
          <Button
            type="text"
            title={collapsed ? "展开导航" : "收起导航"}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((value) => !value)}
          />
          {!compactHeader && <DatabaseOutlined style={{ color: token.colorTextSecondary }} />}
          <Text strong ellipsis style={{ minWidth: 0 }}>{compactHeader ? "管理后台" : "Spider XHS 管理后台"}</Text>
          {!compactHeader && <Text type="secondary" style={{ fontSize: 12, marginLeft: "auto" }}>系统级视图</Text>}
        </Header>
        <Content style={{ padding: "20px clamp(16px, 2.5vw, 28px)", minHeight: "calc(100vh - 49px)", overflow: "auto" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
