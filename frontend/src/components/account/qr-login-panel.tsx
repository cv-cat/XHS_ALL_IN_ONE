import { Alert, Button, Card, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import axios from "axios";
import { useEffect, useRef, useState } from "react";

import { createXhsCreatorQrLoginSession, createXhsPcQrLoginSession, pollXhsLoginSession } from "../../lib/api";
import type { PlatformAccount, XhsQrLoginSession } from "../../types";

const { Text, Link: AntLink } = Typography;

type QrLoginPanelProps = {
  accountType: "pc" | "creator";
  onConfirmed: (account: PlatformAccount) => void;
};

export function QrLoginPanel({ accountType, onConfirmed }: QrLoginPanelProps) {
  const [session, setSession] = useState<XhsQrLoginSession | null>(null);
  const [statusText, setStatusText] = useState("准备生成二维码");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmedRef = useRef(false);

  function errorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (typeof detail === "string" && detail) {
        return detail;
      }
    }
    return "二维码生成失败，请稍后重试。";
  }

  async function startSession() {
    setIsLoading(true);
    setError(null);
    confirmedRef.current = false;
    try {
      const nextSession = accountType === "pc" ? await createXhsPcQrLoginSession() : await createXhsCreatorQrLoginSession();
      setSession(nextSession);
      setStatusText(accountType === "pc" ? "请使用小红书 App 扫描二维码" : "请使用小红书 App 扫描 Creator 二维码");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void startSession();
  }, [accountType]);

  useEffect(() => {
    if (!session?.session_id || session.status === "confirmed" || session.status === "expired") {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const polled = await pollXhsLoginSession(session.session_id);
        setSession((current) => ({
          ...polled,
          qr_image_data_url: polled.qr_image_data_url ?? current?.qr_image_data_url
        }));
        if (polled.status === "scanned") {
          setStatusText("已扫码，请在手机端确认登录");
        } else if (polled.status === "expired") {
          setStatusText("二维码已过期，请刷新");
        } else if (polled.status === "confirmed" && polled.account && !confirmedRef.current) {
          confirmedRef.current = true;
          setStatusText("账号绑定成功");
          onConfirmed(polled.account);
        }
      } catch {
        setError("轮询登录状态失败，正在等待下一次尝试。");
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [accountType, onConfirmed, session?.session_id, session?.status]);

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Card
        styles={{
          body: {
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
            minHeight: 220,
            background: "#1f1f1f",
          },
        }}
        style={{ borderColor: "#303030" }}
      >
        {session?.qr_image_data_url ? (
          <img
            src={session.qr_image_data_url}
            alt="小红书登录二维码"
            style={{ width: 180, height: 180, borderRadius: 8, background: "#fff", padding: 8 }}
          />
        ) : (
          <div
            style={{
              width: 180,
              height: 180,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#262626",
              borderRadius: 8,
              color: "rgba(255,255,255,0.3)",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            QR
          </div>
        )}
      </Card>

      <div style={{ textAlign: "center" }}>
        <Text strong style={{ display: "block", marginBottom: 4, color: "rgba(255,255,255,0.88)" }}>
          {statusText}
        </Text>
        {session?.qr_url ? (
          <AntLink href={session.qr_url} target="_blank" rel="noreferrer">
            打开二维码链接
          </AntLink>
        ) : null}
      </div>

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Button
        block
        icon={<ReloadOutlined />}
        onClick={startSession}
        loading={isLoading}
      >
        {isLoading ? "生成中..." : "刷新二维码"}
      </Button>
    </Space>
  );
}
