import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Result, Typography } from "antd";
import { useNavigate, useParams } from "react-router-dom";

import { getPlatform } from "../../lib/platforms";

const { Paragraph } = Typography;

export function ComingSoonPage() {
  const { platformId } = useParams();
  const platform = getPlatform(platformId);
  const navigate = useNavigate();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "#0a0a0a",
      }}
    >
      <Result
        icon={
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 18,
              background: platform.accent_color,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              fontSize: 36,
              color: "#fff",
              margin: "0 auto 8px",
            }}
          >
            {platform.name_cn.slice(0, 1)}
          </div>
        }
        title={`${platform.name_cn} 工作区即将开放`}
        subTitle={`${platform.name_en} 已进入平台注册表。`}
        extra={
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate("/platform-select")}
          >
            返回平台选择
          </Button>
        }
      >
        <Paragraph type="secondary" style={{ textAlign: "center", maxWidth: 480, margin: "0 auto" }}>
          第一版先完整实现小红书链路，后续平台会沿用同一账号、任务、内容库和发布架构扩展。
        </Paragraph>
      </Result>
    </div>
  );
}
