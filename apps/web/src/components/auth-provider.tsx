"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ApiError, refreshAccessToken, request, type Me } from "@/lib/api";

type Status = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: Status;
  me: Me | null;
  login: (email: string, password: string) => Promise<void>;
  register: (fullName: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  createClub: (name: string) => Promise<void>;
  /** Authenticated API call, relative to /api/v1. */
  api: <T>(
    path: string,
    options?: { method?: string; body?: unknown },
  ) => Promise<T>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [me, setMe] = useState<Me | null>(null);
  // The access token lives in memory only, never in localStorage.
  const token = useRef<string | null>(null);

  /** Authenticated call that refreshes the access token once if it expired. */
  const authed = useCallback(
    async <T,>(path: string, options: { method?: string; body?: unknown } = {}) => {
      try {
        return await request<T>(path, { ...options, token: token.current });
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
        token.current = await refreshAccessToken();
        if (!token.current) {
          setMe(null);
          setStatus("anonymous");
          throw error;
        }
        return await request<T>(path, { ...options, token: token.current });
      }
    },
    [],
  );

  const loadMe = useCallback(async () => {
    setMe(await authed<Me>("/auth/me"));
    setStatus("authenticated");
  }, [authed]);

  useEffect(() => {
    let cancelled = false;
    refreshAccessToken().then(async (accessToken) => {
      if (cancelled) return;
      if (!accessToken) {
        setStatus("anonymous");
        return;
      }
      token.current = accessToken;
      try {
        await loadMe();
      } catch {
        if (!cancelled) setStatus("anonymous");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadMe]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      me,
      async login(email, password) {
        const data = await request<{ access_token: string }>("/auth/login", {
          method: "POST",
          body: { email, password },
        });
        token.current = data.access_token;
        await loadMe();
      },
      async register(fullName, email, password) {
        const data = await request<{ access_token: string }>("/auth/register", {
          method: "POST",
          body: { full_name: fullName, email, password },
        });
        token.current = data.access_token;
        await loadMe();
      },
      async logout() {
        try {
          await request<void>("/auth/logout", { method: "POST" });
        } finally {
          token.current = null;
          setMe(null);
          setStatus("anonymous");
        }
      },
      async createClub(name) {
        await authed("/organizations", { method: "POST", body: { name } });
        await loadMe();
      },
      api: authed,
    }),
    [status, me, loadMe, authed],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
