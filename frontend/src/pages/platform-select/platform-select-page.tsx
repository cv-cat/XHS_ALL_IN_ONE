import { ControlOutlined, LogoutOutlined } from "@ant-design/icons";
import { Button, Space, Typography, theme } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PlatformSelector } from "../../components/layout/platform-selector";
import { useAuth } from "../../hooks/use-auth";
import { fetchPlatforms } from "../../lib/api";
import { fallbackPlatforms } from "../../lib/platforms";
import type { PlatformMeta } from "../../types";

const { Title, Text } = Typography;

export function PlatformSelectPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const [platforms, setPlatforms] = useState<PlatformMeta[]>(fallbackPlatforms);

  useEffect(() => {
    fetchPlatforms().then(setPlatforms);
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: token.colorBgLayout,
        padding: "clamp(24px, 6vw, 48px) clamp(16px, 5vw, 40px)",
      }}
    >
      <div
        style={{
          maxWidth: 960,
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 40,
          }}
        >
          <div>
            <Text
              type="secondary"
              style={{
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: 1,
                display: "block",
                marginBottom: 4,
              }}
            >
              Choose Workspace
            </Text>
            <Title level={2} style={{ margin: "0 0 8px" }}>
              选择平台工作区
            </Title>
            <Text type="secondary">
              小红书已开放，其它平台保留扩展入口。
            </Text>
          </div>
          <Space wrap>
            {auth.user?.is_admin && (
              <Button type="primary" icon={<ControlOutlined />} onClick={() => navigate("/admin/overview")}>
                管理后台
              </Button>
            )}
            <Button icon={<LogoutOutlined />} onClick={() => void auth.logout()}>
              退出登录
            </Button>
          </Space>
        </div>

        <PlatformSelector platforms={platforms} />
      </div>
    </div>
  );
}
