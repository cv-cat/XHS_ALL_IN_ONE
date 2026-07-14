import { Alert, Button, Checkbox, Form, Input, Space } from "antd";
import { ImportOutlined } from "@ant-design/icons";
import { useState } from "react";

import { importXhsCookieAccount } from "../../lib/api";
import type { PlatformAccount } from "../../types";

type CookieImportPanelProps = {
  accountType: "pc" | "creator" | "rednote_pc";
  onImported: (account: PlatformAccount) => void;
};

export function CookieImportPanel({ accountType, onImported }: CookieImportPanelProps) {
  const [cookieString, setCookieString] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncCreator, setSyncCreator] = useState(false);
  const [expectedExternalUserId, setExpectedExternalUserId] = useState("");
  const [expectedNickname, setExpectedNickname] = useState("");
  const isRednote = accountType === "rednote_pc";

  async function handleImport() {
    setError(null);
    if (!cookieString.includes("=")) {
      setError("请粘贴完整 Cookie 字符串。");
      return;
    }
    if (isRednote && !expectedExternalUserId.trim()) {
      setError("请输入当前 Rednote 登录账号的用户 ID，用于防止绑定到错误身份。");
      return;
    }

    setIsSubmitting(true);
    try {
      const account = await importXhsCookieAccount({
        sub_type: accountType,
        cookie_string: cookieString.trim(),
        sync_creator: accountType === "pc" ? syncCreator : undefined,
        expected_external_user_id: isRednote ? expectedExternalUserId.trim() : undefined,
        expected_nickname: isRednote && expectedNickname.trim() ? expectedNickname.trim() : undefined
      });
      onImported(account);
      setCookieString("");
    } catch (err) {
      const apiError = err as {
        response?: { data?: { detail?: string } };
      };
      setError(apiError.response?.data?.detail || "Cookie 无效或已过期。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {isRednote ? (
        <Alert
          type="info"
          showIcon
          message="实验性 Rednote PC 支持"
          description="支持导入你自己的现有 Web 登录 Cookie、账号健康检查，以及公开主页笔记列表和单篇笔记详情采集；不支持二维码、短信登录、搜索、评论、监控或发布。"
        />
      ) : null}

      <Form layout="vertical">
        <Form.Item label={<span style={{ color: "rgba(255,255,255,0.88)" }}>Cookie 字符串</span>}>
          <Input.TextArea
            value={cookieString}
            onChange={(e) => setCookieString(e.target.value)}
            placeholder="a1=...; web_session=...;"
            rows={6}
            style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
          />
        </Form.Item>

        {isRednote ? (
          <>
            <Form.Item
              required
              label={<span style={{ color: "rgba(255,255,255,0.88)" }}>预期 Rednote 用户 ID</span>}
              extra="通常是你当前登录账号主页 URL 中 /user/profile/ 后的 ID。"
            >
              <Input
                value={expectedExternalUserId}
                onChange={(event) => setExpectedExternalUserId(event.target.value)}
                placeholder="your-rednote-user-id"
                style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
              />
            </Form.Item>
            <Form.Item
              label={<span style={{ color: "rgba(255,255,255,0.88)" }}>预期昵称（可选）</span>}
            >
              <Input
                value={expectedNickname}
                onChange={(event) => setExpectedNickname(event.target.value)}
                placeholder="用于额外身份核对"
                style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
              />
            </Form.Item>
          </>
        ) : null}
      </Form>

      {accountType === "pc" ? (
        <Checkbox
          checked={syncCreator}
          onChange={(event) => setSyncCreator(event.target.checked)}
          style={{ color: "rgba(255,255,255,0.88)" }}
        >
          导入 PC Cookie 后同步 Creator 账号
        </Checkbox>
      ) : null}

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Button
        type="primary"
        block
        icon={<ImportOutlined />}
        onClick={handleImport}
        loading={isSubmitting}
      >
        {isSubmitting ? "校验中..." : "校验并导入"}
      </Button>
    </Space>
  );
}
