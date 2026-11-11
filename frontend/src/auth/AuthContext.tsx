import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, onSessionChange, refreshSession, setSession } from "../api/client";
import type { LoginResult, SessionResult, User } from "../api/types";

type AuthValue = {
  /** False until the first refresh attempt on page load has finished. */
  ready: boolean;
  user: User | null;
  login: (email: string, password: string) => Promise<LoginResult>;
  loginMfa: (ticket: string, code: string) => Promise<User>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<User | null>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const off = onSessionChange(({ user: next }) => setUser(next));
    refreshSession().finally(() => setReady(true));
    return off;
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api<LoginResult>("/api/auth/login", { body: { email, password }, auth: false });
    if (result.status === "ok") setSession(result.access_token, result.user);
    return result;
  }, []);

  const loginMfa = useCallback(async (ticket: string, code: string) => {
    const result = await api<SessionResult>("/api/auth/login/mfa", {
      body: { mfa_ticket: ticket, code },
      auth: false,
    });
    setSession(result.access_token, result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api<void>("/api/auth/logout", { method: "POST", auth: false });
    } catch {
      // signing out locally is enough if the server is unreachable
    } finally {
      setSession(null, null);
    }
  }, []);

  const reloadUser = useCallback(async () => {
    try {
      const me = await api<User>("/api/auth/me");
      setUser(me);
      return me;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo(
    () => ({ ready, user, login, loginMfa, logout, reloadUser }),
    [ready, user, login, loginMfa, logout, reloadUser],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthValue {
  const value = use(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
