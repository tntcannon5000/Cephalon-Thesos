import { apiFetch } from "./http";

export interface AdminOverview {
  users: number;
  active_users: number;
  pending_access_requests: number;
  pending_quota_requests: number;
  runs_today: number;
  tokens_today: number;
  estimated_cost_usd_today: string;
  active_runs: number;
  live_workers: number;
}

export interface AdminUser {
  id: string;
  email: string;
  status: string;
  roles: string[];
  daily_run_limit: number | null;
  runs_today: number;
  created_at: string;
}

export interface AccessRequest {
  id: string;
  email: string;
  status: string;
  created_at: string;
}

export interface QuotaRequest {
  id: string;
  user_id: string;
  email: string;
  requested_units: number;
  reason: string;
  status: string;
  created_at: string;
}

export interface MFASetup {
  secret: string;
  provisioning_uri: string;
}

export type MetricsPeriod = "15m" | "hour" | "day" | "week" | "month" | "year";

export interface MetricPoint {
  started_at: string;
  attempts: number;
  runs: number;
  request_tokens: number;
  response_tokens: number;
  total_tokens: number;
  estimated_cost_usd: string;
}

export interface UserUsage {
  user_id: string;
  email: string;
  runs: number;
  total_tokens: number;
  estimated_cost_usd: string;
}

export interface ModelUsage {
  provider: string;
  model: string;
  attempts: number;
  total_tokens: number;
  estimated_cost_usd: string;
  average_latency_ms: number | null;
}

export interface AdminMetrics {
  period: MetricsPeriod;
  starts_at: string;
  ends_at: string;
  attempts: number;
  runs: number;
  request_tokens: number;
  response_tokens: number;
  total_tokens: number;
  estimated_cost_usd: string;
  points: MetricPoint[];
  users: UserUsage[];
  models: ModelUsage[];
}

export async function loadAdminData() {
  const [overview, users, accessRequests, quotaRequests] = await Promise.all([
    apiFetch<AdminOverview>("/api/v1/admin/overview"),
    apiFetch<AdminUser[]>("/api/v1/admin/users"),
    apiFetch<AccessRequest[]>("/api/v1/admin/access-requests"),
    apiFetch<QuotaRequest[]>("/api/v1/admin/quota-requests"),
  ]);
  return { overview, users, accessRequests, quotaRequests };
}

export function loadAdminMetrics(period: MetricsPeriod): Promise<AdminMetrics> {
  return apiFetch<AdminMetrics>(`/api/v1/admin/metrics?period=${period}`);
}

export function startMFA(): Promise<MFASetup> {
  return apiFetch<MFASetup>("/api/v1/admin/mfa/setup", { method: "POST" });
}

export async function confirmMFA(code: string): Promise<string[]> {
  const response = await apiFetch<{ recovery_codes: string[] }>("/api/v1/admin/mfa/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  return response.recovery_codes;
}

export async function addAllowlist(email: string, role: "admin" | null): Promise<void> {
  await apiFetch("/api/v1/admin/allowlist", {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export async function resolveAccess(id: string, resolution: "approved" | "denied") {
  await apiFetch(`/api/v1/admin/access-requests/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution, grant_units: null }),
  });
}

export async function resolveQuota(
  id: string,
  resolution: "approved" | "denied",
  grantUnits?: number,
) {
  await apiFetch(`/api/v1/admin/quota-requests/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution, grant_units: grantUnits ?? null }),
  });
}

export async function updateUserStatus(id: string, status: "active" | "suspended" | "revoked") {
  await apiFetch(`/api/v1/admin/users/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
