import { useCallback, useEffect, useMemo, useState, type PropsWithChildren } from "react";

import { apiFetch, HttpError } from "../../transport/http";
import { AuthContext } from "./AuthContext";
import type { AuthStatus, AuthUser, PublicAuthConfig, UserPreferences } from "./types";

interface MessageResponse {
  message: string;
}

const DEFAULT_CONFIG: PublicAuthConfig = {
  terms_version: "2026-08-17-private-alpha",
  turnstile_site_key: null,
};

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [config, setConfig] = useState<PublicAuthConfig>(DEFAULT_CONFIG);

  const refresh = useCallback(async () => {
    try {
      const account = await apiFetch<AuthUser>("/api/v1/me");
      setUser(account);
      setStatus("authenticated");
      return account;
    } catch (error) {
      if (error instanceof HttpError && error.status === 401) {
        setUser(null);
        setStatus("anonymous");
        return null;
      }
      setStatus("anonymous");
      throw error;
    }
  }, []);

  useEffect(() => {
    let active = true;
    void apiFetch<PublicAuthConfig>("/api/v1/auth/config")
      .then((publicConfig) => {
        if (active) setConfig(publicConfig);
        return apiFetch<AuthUser>("/api/v1/me");
      })
      .then((account) => {
        if (!active) return;
        setUser(account);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) return;
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo(
    () => ({
      status,
      user,
      config,
      refresh,
      async login(email: string, password: string, mfaCode?: string) {
        await apiFetch<MessageResponse>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password, mfa_code: mfaCode || null }),
        });
        await refresh();
      },
      async logout() {
        await apiFetch<MessageResponse>("/api/v1/auth/logout", { method: "POST" });
        setUser(null);
        setStatus("anonymous");
      },
      async register(email: string, password: string, confirmation: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/register", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            password_confirmation: confirmation,
            accept_terms: true,
            terms_version: config.terms_version,
          }),
        });
        return result.message;
      },
      async requestAccess(email: string, turnstileToken?: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/access-requests", {
          method: "POST",
          body: JSON.stringify({ email, turnstile_token: turnstileToken || null }),
        });
        return result.message;
      },
      async resendVerification(email: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/resend-verification", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        return result.message;
      },
      async forgotPassword(email: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/password/forgot", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        return result.message;
      },
      async verifyEmail(token: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/verify-email", {
          method: "POST",
          body: JSON.stringify({ token }),
        });
        return result.message;
      },
      async resetPassword(token: string, password: string, confirmation: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/password/reset", {
          method: "POST",
          body: JSON.stringify({ token, password, password_confirmation: confirmation }),
        });
        return result.message;
      },
      async changePassword(current: string, password: string, confirmation: string) {
        const result = await apiFetch<MessageResponse>("/api/v1/auth/password/change", {
          method: "POST",
          body: JSON.stringify({
            current_password: current,
            password,
            password_confirmation: confirmation,
          }),
        });
        return result.message;
      },
      async updatePreferences(preferences: Partial<UserPreferences>) {
        const updated = await apiFetch<UserPreferences>("/api/v1/me/preferences", {
          method: "PATCH",
          body: JSON.stringify(preferences),
        });
        setUser((current) => (current ? { ...current, preferences: updated } : current));
      },
    }),
    [config, refresh, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
