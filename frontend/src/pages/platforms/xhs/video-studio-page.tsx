import { ReloadOutlined, VideoCameraOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Typography } from "antd";

import { PageHeader } from "../../../components/layout/app-shell";

const { Text } = Typography;

export function XhsVideoStudioPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PageHeader
        eyebrow="XHS Video Studio"
        title="视频工坊"
        description="视频剪辑、封面提取、视频转码和 AI 视频处理工具。"
        action={<Button icon={<ReloadOutlined />} disabled>刷新</Button>}
      />

      <Card
        style={{ background: "#1a1a1a", borderRadius: 8, border: "1px solid #303030" }}
        styles={{ body: { padding: 48 } }}
      >
        <Empty
          image={<VideoCameraOutlined style={{ fontSize: 64, color: "#8c8c8c" }} />}
          imageStyle={{ height: 80 }}
          description={
            <div>
              <Text strong style={{ fontSize: 16, display: "block", marginBottom: 8 }}>视频工坊即将上线</Text>
              <Text type="secondary">
                视频剪辑、封面提取、视频转码、AI 视频润色等功能正在开发中，敬请期待。
              </Text>
            </div>
          }
        />
      </Card>
    </div>
  );
}
