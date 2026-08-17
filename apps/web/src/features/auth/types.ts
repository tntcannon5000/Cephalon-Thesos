export interface Allowance {
  day: string;
  limit: number;
  used: number;
  remaining: number;
  reset_at: string;
}

export interface UserPreferences {
  display_name: string | null;
  theme_id: string | null;
  sidebar_width: number | null;
}

export interface AuthUser {
  id: string;
  email: string;
  status: string;
  roles: string[];
  admin_mfa_enrolled: boolean;
  terms_version: string;
  allowance: Allowance;
  preferences: UserPreferences;
}

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export interface PublicAuthConfig {
  terms_version: string;
  turnstile_site_key: string | null;
}

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  config: PublicAuthConfig;
  refresh: () => Promise<AuthUser | null>;
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (email: string, password: string, confirmation: string) => Promise<string>;
  resendVerification: (email: string) => Promise<string>;
  requestAccess: (email: string, turnstileToken?: string) => Promise<string>;
  forgotPassword: (email: string) => Promise<string>;
  verifyEmail: (token: string) => Promise<string>;
  resetPassword: (token: string, password: string, confirmation: string) => Promise<string>;
  changePassword: (current: string, password: string, confirmation: string) => Promise<string>;
  updatePreferences: (preferences: Partial<UserPreferences>) => Promise<void>;
}
