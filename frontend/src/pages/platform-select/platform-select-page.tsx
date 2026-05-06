import { LogoutOutlined } from "@ant-design/icons";
import { Button, Space, Typography } from "antd";
import { useEffect, useState } from "react";

import { PlatformSelector } from "../../components/layout/platform-selector";
import { useAuth } from "../../hooks/use-auth";
import { fetchPlatforms } from "../../lib/api";
import { fallbackPlatforms } from "../../lib/platforms";
import type { PlatformMeta } from "../../types";

const { Title, Text } = Typography;

export function PlatformSelectPage() {
  const auth = useAuth();
  const [platforms, setPlatforms] = useState<PlatformMeta[]>(fallbackPlatforms);

  useEffect(() => {
    fetchPlatforms().then(setPlatforms);
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0a0a",
        padding: "48px 40px",
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
          <Button
            icon={<LogoutOutlined />}
            onClick={() => void auth.logout()}
          >
            退出登录
          </Button>
        </div>

        <PlatformSelector platforms={platforms} />
      </div>
    </div>
  );
}
