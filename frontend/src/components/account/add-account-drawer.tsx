import { Drawer, Segmented, message } from "antd";
import { useEffect, useState } from "react";

import type { PlatformAccount } from "../../types";
import { CookieImportPanel } from "./cookie-import-panel";
import { PhoneLoginPanel } from "./phone-login-panel";
import { QrLoginPanel } from "./qr-login-panel";

type AddAccountDrawerProps = {
  open: boolean;
  onClose: () => void;
  onBound: () => void;
};

type AccountType = "pc" | "creator" | "rednote_pc";
type XhsLoginAccountType = Exclude<AccountType, "rednote_pc">;
type LoginMethod = "qr" | "phone" | "cookie";

const accountTypeOptions = [
  { label: "PC", value: "pc" as const },
  { label: "Creator", value: "creator" as const },
  { label: "Rednote PC", value: "rednote_pc" as const },
];

const loginMethodOptions = [
  { label: "二维码", value: "qr" as const },
  { label: "手机验证码", value: "phone" as const },
  { label: "Cookie", value: "cookie" as const },
];

export function AddAccountDrawer({ open, onClose, onBound }: AddAccountDrawerProps) {
  const [accountType, setAccountType] = useState<AccountType>("pc");
  const [method, setMethod] = useState<LoginMethod>("qr");

  function handleConfirmed(account: PlatformAccount) {
    const actionText = account.action === "updated" ? "已更新到账号矩阵" : "已加入账号矩阵";
    message.success(`${account.nickname || "账号"} ${actionText}`);
    onBound();
  }

  useEffect(() => {
    if (accountType === "rednote_pc") {
      setMethod("cookie");
    }
  }, [accountType]);

  const availableLoginMethods = accountType === "rednote_pc"
    ? loginMethodOptions.filter((option) => option.value === "cookie")
    : loginMethodOptions;

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            XHS / Rednote Account
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color: "rgba(255,255,255,0.88)" }}>添加账号</div>
        </div>
      }
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        header: { background: "#1f1f1f", borderBottom: "1px solid #303030" },
        body: { background: "#141414", padding: 24 },
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
          options={availableLoginMethods}
          onChange={(val) => setMethod(val as LoginMethod)}
        />
      </div>

      {accountType === "rednote_pc" ? (
        <CookieImportPanel key={accountType} accountType={accountType} onImported={handleConfirmed} />
      ) : method === "qr" ? (
        <QrLoginPanel accountType={accountType as XhsLoginAccountType} onConfirmed={handleConfirmed} />
      ) : method === "cookie" ? (
        <CookieImportPanel key={accountType} accountType={accountType} onImported={handleConfirmed} />
      ) : (
        <PhoneLoginPanel accountType={accountType as XhsLoginAccountType} onConfirmed={handleConfirmed} />
      )}
    </Drawer>
  );
}
