import { ArrowRightOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { Card, Col, Row, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";

import type { PlatformMeta } from "../../types";

const { Text, Title } = Typography;

export function PlatformSelector({ platforms }: { platforms: PlatformMeta[] }) {
  const navigate = useNavigate();

  return (
    <Row gutter={[20, 20]}>
      {platforms.map((platform) => {
        const href = platform.enabled
          ? `/platforms/${platform.id}/dashboard`
          : `/platforms/${platform.id}`;

        return (
          <Col key={platform.id} xs={24} sm={12} md={8} lg={8}>
            <Card
              hoverable
              style={{
                borderColor: "#303030",
                cursor: "pointer",
              }}
              styles={{
                body: { padding: "20px 24px" },
              }}
              onClick={() => navigate(href)}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    background: platform.accent_color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 800,
                    fontSize: 20,
                    color: "#fff",
                    flexShrink: 0,
                  }}
                >
                  {platform.name_cn.slice(0, 1)}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <Title level={5} style={{ margin: 0, fontSize: 16 }}>
                    {platform.name_cn}
                  </Title>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {platform.name_en}
                  </Text>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <Tag
                    color={platform.enabled ? "blue" : "default"}
                    style={{
                      margin: 0,
                      borderRadius: 4,
                    }}
                  >
                    {platform.enabled ? "Active" : "Coming Soon"}
                  </Tag>
                  {platform.enabled ? (
                    <ArrowRightOutlined
                      style={{ color: "rgba(255,255,255,0.45)", fontSize: 14 }}
                    />
                  ) : (
                    <ClockCircleOutlined
                      style={{ color: "rgba(255,255,255,0.25)", fontSize: 14 }}
                    />
                  )}
                </div>
              </div>
            </Card>
          </Col>
        );
      })}
    </Row>
  );
}
