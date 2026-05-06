import { Alert, Button, Checkbox, Form, Input, Space } from "antd";
import { ImportOutlined } from "@ant-design/icons";
import { useState } from "react";

import { importXhsCookieAccount } from "../../lib/api";
import type { PlatformAccount } from "../../types";

type CookieImportPanelProps = {
  accountType: "pc" | "creator";
  onImported: (account: PlatformAccount) => void;
};

export function CookieImportPanel({ accountType, onImported }: CookieImportPanelProps) {
  const [cookieString, setCookieString] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncCreator, setSyncCreator] = useState(false);

  async function handleImport() {
    setError(null);
    if (!cookieString.includes("=")) {
      setError("请粘贴完整 Cookie 字符串。");
      return;
    }

    setIsSubmitting(true);
    try {
      const account = await importXhsCookieAccount({
        sub_type: accountType,
        cookie_string: cookieString.trim(),
        sync_creator: accountType === "pc" ? syncCreator : undefined
      });
      onImported(account);
      setCookieString("");
    } catch {
      setError("Cookie 无效或已过期。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
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
