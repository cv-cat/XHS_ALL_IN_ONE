import { Alert, Button, Card, Checkbox, Space, Typography } from "antd";
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
  const [syncCreator, setSyncCreator] = useState(false);
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
      const nextSession =
        accountType === "pc"
          ? await createXhsPcQrLoginSession({ sync_creator: syncCreator })
          : await createXhsCreatorQrLoginSession();
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
  }, [accountType, syncCreator]);

  const onConfirmedRef = useRef(onConfirmed);
  useEffect(() => {
    onConfirmedRef.current = onConfirmed;
  }, [onConfirmed]);

  useEffect(() => {
    const sessionId = session?.session_id;
    if (!sessionId || session?.status === "confirmed" || session?.status === "expired") {
      return;
    }

    let cancelled = false;
    let inFlight = false;

    const poll = async () => {
      if (inFlight || cancelled) return;
      inFlight = true;
      try {
        const polled = await pollXhsLoginSession(sessionId);
        if (cancelled) return;
        setSession((current) => ({
          ...polled,
          qr_image_data_url: polled.qr_image_data_url ?? current?.qr_image_data_url
        }));
        setError(null);
        if (polled.status === "scanned") {
          setStatusText("已扫码，请在手机端点「确认登录」");
        } else if (polled.status === "expired") {
          setStatusText("二维码已过期，请刷新");
        } else if (polled.status === "confirmed") {
          if (polled.account && !confirmedRef.current) {
            confirmedRef.current = true;
            setStatusText("账号绑定成功");
            onConfirmedRef.current(polled.account);
          } else if (!polled.account) {
            setStatusText(polled.error || "已确认登录，但账号信息读取失败，请重试或改用 Cookie 导入");
            setError(polled.error || "账号信息读取失败，可改用 Cookie 导入");
          }
        }
      } catch {
        if (!cancelled) {
          setError("轮询登录状态失败，正在等待下一次尝试。");
        }
      } finally {
        inFlight = false;
      }
    };

    void poll();
    const interval = window.setInterval(poll, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [session?.session_id, session?.status]);

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

      {accountType === "pc" ? (
        <Checkbox
          checked={syncCreator}
          onChange={(event) => setSyncCreator(event.target.checked)}
          style={{ color: "rgba(255,255,255,0.88)" }}
        >
          登录 PC 后同步 Creator 账号
        </Checkbox>
      ) : null}

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
