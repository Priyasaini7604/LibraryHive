"use client";

/**
 * Session state for the whole app (UI_ARCHITECTURE.md 9.4, SEC-1).
 *
 * On load the session is restored from the HttpOnly refresh cookie; the access
 * token is kept in memory only. Logging out in one tab signs out other tabs
 * through a BroadcastChannel (no token is ever written to storage).
 */

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import * as authApi from "./api/auth";
import { onSessionExpired } from "./api-client";
import { tokenStore } from "./auth";
import type { User } from "./types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  /** Reload the current user (e.g. after a profile change or library creation). */
  reloadUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const CHANNEL = "libraryhive-auth";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const channelRef = useRef<BroadcastChannel | null>(null);

  const signOutLocally = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  const reloadUser = useCallback(async () => {
    const me = await authApi.fetchMe();
    setUser(me);
    setStatus("authenticated");
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const restored = await authApi.restoreSession();
      if (cancelled) return;
      if (!restored) {
        setStatus("anonymous");
        return;
      }
      try {
        const me = await authApi.fetchMe();
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) signOutLocally();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [signOutLocally]);

  useEffect(() => {
    onSessionExpired(signOutLocally);
    return () => onSessionExpired(null);
  }, [signOutLocally]);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const channel = new BroadcastChannel(CHANNEL);
    channel.onmessage = (event: MessageEvent<string>) => {
      if (event.data === "logout") signOutLocally();
    };
    channelRef.current = channel;
    return () => channel.close();
  }, [signOutLocally]);

  const login = useCallback(async (email: string, password: string) => {
    const loggedIn = await authApi.login(email, password);
    setUser(loggedIn);
    setStatus("authenticated");
    return loggedIn;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      signOutLocally();
      channelRef.current?.postMessage("logout");
    }
  }, [signOutLocally]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, reloadUser }),
    [status, user, login, logout, reloadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>.");
  return context;
}
