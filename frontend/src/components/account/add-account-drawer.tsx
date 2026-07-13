import { Drawer, Segmented, message, theme } from "antd";
import { useState } from "react";

import type { PlatformAccount } from "../../types";
import { CookieImportPanel } from "./cookie-import-panel";
import { PhoneLoginPanel } from "./phone-login-panel";
import { QrLoginPanel } from "./qr-login-panel";

type AddAccountDrawerProps = {
  open: boolean;
  onClose: () => void;
  onBound: () => void;
};

type AccountType = "pc" | "creator";
type LoginMethod = "qr" | "phone" | "cookie";

const accountTypeOptions = [
  { label: "PC", value: "pc" as const },
  { label: "Creator", value: "creator" as const },
];

const loginMethodOptions = [
  { label: "二维码", value: "qr" as const },
  { label: "手机验证码", value: "phone" as const },
  { label: "Cookie", value: "cookie" as const },
];

export function AddAccountDrawer({ open, onClose, onBound }: AddAccountDrawerProps) {
  const { token } = theme.useToken();
  const [accountType, setAccountType] = useState<AccountType>("pc");
  const [method, setMethod] = useState<LoginMethod>("qr");

  function handleConfirmed(account: PlatformAccount) {
    const actionText = account.action === "updated" ? "已更新到账号矩阵" : "已加入账号矩阵";
    message.success(`${account.nickname || "账号"} ${actionText}`);
    onBound();
  }

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 12, color: token.colorTextSecondary, marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            XHS Account
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color: token.colorText }}>添加小红书账号</div>
        </div>
      }
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        header: { background: token.colorBgElevated, borderBottom: `1px solid ${token.colorSplit}` },
        body: { background: token.colorBgLayout, padding: 24 },
      }}
    >
      <div style={{ marginBottom: 20 }}>
        <Segmented
          block
          value={accountType}
          options={accountTypeOptions}
          onChange={(val) => setAccountType(val as AccountType)}
        />
      </div>

      <div style={{ marginBottom: 24 }}>
        <Segmented
          block
          value={method}
          options={loginMethodOptions}
          onChange={(val) => setMethod(val as LoginMethod)}
        />
      </div>

      {method === "qr" ? (
        <QrLoginPanel accountType={accountType} onConfirmed={handleConfirmed} />
      ) : method === "cookie" ? (
        <CookieImportPanel accountType={accountType} onImported={handleConfirmed} />
      ) : (
        <PhoneLoginPanel accountType={accountType} onConfirmed={handleConfirmed} />
      )}
    </Drawer>
  );
}
