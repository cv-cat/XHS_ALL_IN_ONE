import axios from "axios";
import { useEffect, useSyncExternalStore } from "react";

import * as api from "../lib/api";
import type { PlatformUser } from "../types";

type AuthStatus = "checking" | "authenticated" | "anonymous";

type AuthSnapshot = {
  status: AuthStatus;
  user: PlatformUser | null;
  error: string | null;
};

let snapshot: AuthSnapshot = {
  status: api.hasRefreshToken() ? "checking" : "anonymous",
  user: null,
  error: null
};

let bootstrapped = false;
const listeners = new Set<() => void>();

function emit(next: AuthSnapshot): void {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): AuthSnapshot {
  return snapshot;
}

function authErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  const detail = error.response?.data?.detail;
  if (detail === "Invalid username or password") {
    return "账号不存在或密码错误，请检查后重试。";
  }
  if (detail === "Username already exists") {
    return "该平台账号已存在，请直接登录或换一个账号。";
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return fallback;
}

async function bootstrap(): Promise<void> {
  if (bootstrapped) {
    return;
  }
  bootstrapped = true;
  if (!api.hasRefreshToken()) {
    emit({ status: "anonymous", user: null, error: null });
    return;
  }

  emit({ ...snapshot, status: "checking", error: null });
  try {
    const user = await api.bootstrapAuth();
    emit(user ? { status: "authenticated", user, error: null } : { status: "anonymous", user: null, error: null });
  } catch {
    api.clearAuthTokens();
    emit({ status: "anonymous", user: null, error: "登录已过期，请重新登录。" });
  }
}

async function login(credentials: api.AuthCredentials): Promise<void> {
  emit({ ...snapshot, error: null });
  try {
    const payload = await api.login(credentials);
    emit({ status: "authenticated", user: payload.user, error: null });
  } catch (error) {
    const message = authErrorMessage(error, "账号不存在或密码错误，请检查后重试。");
    emit({ status: "anonymous", user: null, error: message });
    throw new Error(message);
  }
}

async function register(credentials: api.AuthCredentials): Promise<void> {
  emit({ ...snapshot, error: null });
  try {
    const payload = await api.register(credentials);
    emit({ status: "authenticated", user: payload.user, error: null });
  } catch (error) {
    const message = authErrorMessage(error, "注册失败，该平台账号可能已存在。");
    emit({ status: "anonymous", user: null, error: message });
    throw new Error(message);
  }
}

async function logout(): Promise<void> {
  await api.logout();
  emit({ status: "anonymous", user: null, error: null });
}

export function useAuth() {
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  useEffect(() => {
    void bootstrap();
  }, []);

  return {
    ...current,
    isAuthenticated: current.status === "authenticated",
    isChecking: current.status === "checking",
    login,
    register,
    logout
  };
}
