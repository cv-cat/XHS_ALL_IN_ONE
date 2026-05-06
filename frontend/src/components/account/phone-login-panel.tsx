import { Alert, Button, Checkbox, Form, Input, Space, Typography } from "antd";
import { MessageOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { confirmXhsPhoneLogin, sendXhsPhoneCode } from "../../lib/api";
import type { PlatformAccount } from "../../types";

const { Text } = Typography;

type PhoneLoginPanelProps = {
  accountType: "pc" | "creator";
  onConfirmed: (account: PlatformAccount) => void;
};

const PHONE_CODE_COOLDOWN_SECONDS = 120;

export function PhoneLoginPanel({ accountType, onConfirmed }: PhoneLoginPanelProps) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [statusText, setStatusText] = useState("输入手机号后发送验证码");
  const [isSending, setIsSending] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [syncCreator, setSyncCreator] = useState(false);
  const isCoolingDown = cooldownSeconds > 0;

  useEffect(() => {
    if (cooldownSeconds <= 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      setCooldownSeconds((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearTimeout(timer);
  }, [cooldownSeconds]);

  async function handleSendCode() {
    setError(null);
    if (isCoolingDown) {
      return;
    }
    if (phone.trim().length < 6) {
      setError("请输入有效手机号。");
      return;
    }

    setIsSending(true);
    try {
      const result = await sendXhsPhoneCode({
        sub_type: accountType,
        phone: phone.trim(),
        sync_creator: accountType === "pc" ? syncCreator : undefined
      });
      setSessionId(result.session_id);
      setStatusText("验证码已发送，请查看手机短信");
      setCooldownSeconds(PHONE_CODE_COOLDOWN_SECONDS);
    } catch {
      setError("验证码发送失败。");
    } finally {
      setIsSending(false);
    }
  }

  async function handleConfirm() {
    setError(null);
    if (!sessionId) {
      setError("请先发送验证码。");
      return;
    }
    if (code.trim().length < 4) {
      setError("请输入短信验证码。");
      return;
    }

    setIsConfirming(true);
    try {
      const result = await confirmXhsPhoneLogin({
        sub_type: accountType,
        session_id: sessionId,
        phone: phone.trim(),
        code: code.trim(),
        sync_creator: accountType === "pc" ? syncCreator : undefined
      });
      if (result.account) {
        onConfirmed(result.account);
      }
      setStatusText("账号绑定成功");
    } catch {
      setError("验证码校验失败或已过期。");
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Text style={{ color: "rgba(255,255,255,0.65)" }}>{statusText}</Text>

      <Form layout="vertical">
        <Form.Item label={<span style={{ color: "rgba(255,255,255,0.88)" }}>手机号</span>}>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="请输入手机号"
            style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
          />
        </Form.Item>
      </Form>

      {accountType === "pc" ? (
        <Checkbox
          checked={syncCreator}
          onChange={(event) => setSyncCreator(event.target.checked)}
          style={{ color: "rgba(255,255,255,0.88)" }}
        >
          登录 PC 后同步 Creator 账号
        </Checkbox>
      ) : null}

      <Button
        block
        icon={<MessageOutlined />}
        onClick={handleSendCode}
        disabled={isSending || isCoolingDown}
        loading={isSending}
      >
        {isSending ? "发送中..." : isCoolingDown ? `${cooldownSeconds} 秒后重发` : "发送验证码"}
      </Button>

      <Form layout="vertical">
        <Form.Item label={<span style={{ color: "rgba(255,255,255,0.88)" }}>验证码</span>}>
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="请输入验证码"
            style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
          />
        </Form.Item>
      </Form>

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Button
        type="primary"
        block
        icon={<CheckCircleOutlined />}
        onClick={handleConfirm}
        loading={isConfirming}
      >
        {isConfirming ? "验证中..." : "确认绑定"}
      </Button>
    </Space>
  );
}
