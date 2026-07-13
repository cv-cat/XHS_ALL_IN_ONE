import { Spin, theme } from "antd";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../../hooks/use-auth";

type RouteGuardProps = {
  children: ReactNode;
};

function RouteLoading({ tip }: { tip: string }) {
  const { token } = theme.useToken();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: token.colorBgLayout,
      }}
    >
      <Spin size="large" tip={tip} />
    </div>
  );
}

export function ProtectedRoute({ children }: RouteGuardProps) {
  const location = useLocation();
  const auth = useAuth();

  if (auth.isChecking) {
    return <RouteLoading tip="正在验证登录状态..." />;
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export function PublicOnlyRoute({ children }: RouteGuardProps) {
  const auth = useAuth();

  if (auth.isChecking) {
    return <RouteLoading tip="正在验证登录状态..." />;
  }

  if (auth.isAuthenticated) {
    return <Navigate to="/platform-select" replace />;
  }

  return <>{children}</>;
}

export function AdminRoute({ children }: RouteGuardProps) {
  const location = useLocation();
  const auth = useAuth();

  if (auth.isChecking) {
    return <RouteLoading tip="正在验证管理员权限..." />;
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!auth.user?.is_admin) {
    return <Navigate to="/platform-select" replace />;
  }

  return <>{children}</>;
}
