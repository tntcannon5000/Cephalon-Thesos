import { ArrowLeft, Check, Plus, X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { AdminMfaControl } from "../components/AdminMfaControl";
import { CostEstimateChart, TokenVolumeChart } from "../components/AdminCharts";
import { useAuth } from "../features/auth/AuthContext";
import {
  addAllowlist,
  loadAdminData,
  loadAdminMetrics,
  resolveAccess,
  resolveQuota,
  updateUserStatus,
  type AccessRequest,
  type AdminMetrics,
  type AdminOverview,
  type AdminUser,
  type MetricsPeriod,
  type QuotaRequest,
} from "../transport/admin";

interface AdminData {
  overview: AdminOverview;
  users: AdminUser[];
  accessRequests: AccessRequest[];
  quotaRequests: QuotaRequest[];
}

const PERIODS: { id: MetricsPeriod; label: string }[] = [
  { id: "15m", label: "15 min" },
  { id: "hour", label: "Hour" },
  { id: "day", label: "Day" },
  { id: "week", label: "Week" },
  { id: "month", label: "Month" },
  { id: "year", label: "Year" },
];

function compactNumber(value: number): string {
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function money(value: string): string {
  const amount = Number(value);
  if (amount === 0) return "$0.00";
  return `$${amount < 0.01 ? amount.toFixed(6) : amount.toFixed(2)}`;
}

export function AdminPage() {
  const auth = useAuth();
  const [data, setData] = useState<AdminData | null>(null);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [period, setPeriod] = useState<MetricsPeriod>("day");
  const [allowlistEmail, setAllowlistEmail] = useState("");
  const [allowlistRole, setAllowlistRole] = useState<"user" | "admin">("user");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setData(await loadAdminData());
      setError(null);
    } catch {
      setError("The administration archive could not be loaded.");
    }
  }, []);

  useEffect(() => {
    if (!auth.user?.roles.includes("admin")) return;
    let active = true;
    void loadAdminData()
      .then((loaded) => {
        if (active) setData(loaded);
      })
      .catch(() => {
        if (active) setError("The administration archive could not be loaded.");
      });
    return () => { active = false; };
  }, [auth.user]);

  useEffect(() => {
    if (!auth.user?.roles.includes("admin")) return;
    let active = true;
    void loadAdminMetrics(period)
      .then((loaded) => {
        if (active) setMetrics(loaded);
      })
      .catch(() => {
        if (active) setError("Usage metrics could not be loaded.");
      });
    return () => { active = false; };
  }, [auth.user, period]);

  if (auth.status === "loading") return <div className="auth-loading"><i /></div>;
  if (!auth.user?.roles.includes("admin")) {
    return <main className="admin-shell"><p>Administration access is unavailable.</p><Link to="/">Return to Thesos</Link></main>;
  }

  const act = async (operation: () => Promise<unknown>, success: string) => {
    try {
      await operation();
      setNotice(success);
      setError(null);
      await reload();
    } catch {
      setError("The requested administration action failed.");
    }
  };

  const addAccess = (event: FormEvent) => {
    event.preventDefault();
    const role = allowlistRole === "admin" ? "admin" : null;
    const message = role ? "Administrator access granted to that address." : "Address added to the allowlist.";
    void act(() => addAllowlist(allowlistEmail, role), message);
    setAllowlistEmail("");
  };

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div><p>THESOS OPERATIONS</p><h1>Private alpha overview</h1></div>
        <Link to="/"><ArrowLeft size={16} /> Return to chat</Link>
      </header>
      {notice ? <motion.p className="admin-notice" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{notice}</motion.p> : null}
      {error ? <p className="admin-error">{error}</p> : null}
      <AdminMfaControl enrolled={auth.user.admin_mfa_enrolled} />

      {data && metrics ? (
        <>
          <div className="admin-range-header">
            <div><span>USAGE WINDOW</span><strong>{new Date(metrics.starts_at).toLocaleString()} – {new Date(metrics.ends_at).toLocaleString()}</strong></div>
            <div className="admin-periods" role="tablist" aria-label="Metrics time range">
              {PERIODS.map((option) => <button role="tab" aria-selected={period === option.id} className={period === option.id ? "is-active" : ""} key={option.id} type="button" onClick={() => setPeriod(option.id)}>{option.label}</button>)}
            </div>
          </div>

          <section className="admin-metrics">
            {[
              ["Active / total users", `${data.overview.active_users.toLocaleString()} / ${data.overview.users.toLocaleString()}`],
              ["Runs", metrics.runs.toLocaleString()],
              ["Provider attempts", metrics.attempts.toLocaleString()],
              ["Total tokens", compactNumber(metrics.total_tokens)],
              ["Estimated cost", money(metrics.estimated_cost_usd)],
              ["Live workers", `${data.overview.live_workers} · ${data.overview.active_runs} active`],
            ].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
          </section>

          <section className="admin-chart-grid">
            <div className="admin-panel admin-chart-panel"><div><h2>Token volume</h2><small>{metrics.request_tokens.toLocaleString()} input · {metrics.response_tokens.toLocaleString()} output</small></div><TokenVolumeChart points={metrics.points} period={period} /></div>
            <div className="admin-panel admin-chart-panel"><div><h2>Estimated provider cost</h2><small>{money(metrics.estimated_cost_usd)} across {metrics.attempts} attempts</small></div><CostEstimateChart points={metrics.points} period={period} /></div>
          </section>

          <section className="admin-grid">
            <div className="admin-panel">
              <div className="admin-panel-title">
                <h2>Users</h2>
                <form onSubmit={addAccess}>
                  <input required type="email" placeholder="Email address" value={allowlistEmail} onChange={(event) => setAllowlistEmail(event.target.value)} />
                  <select aria-label="Access role" value={allowlistRole} onChange={(event) => setAllowlistRole(event.target.value as "user" | "admin")}><option value="user">User</option><option value="admin">Administrator</option></select>
                  <button type="submit" aria-label="Grant access"><Plus size={14} /> Add</button>
                </form>
              </div>
              <div className="admin-table">{data.users.map((user) => <div className="admin-row" key={user.id}><span><strong>{user.email}</strong><small>{user.status} · {user.roles.join(", ") || "user"} · {user.runs_today} runs today</small></span>{user.id !== auth.user?.id ? <button type="button" onClick={() => void act(() => updateUserStatus(user.id, user.status === "active" ? "suspended" : "active"), user.status === "active" ? "Account suspended." : "Account activated.")}>{user.status === "active" ? "Suspend" : "Activate"}</button> : <small>You</small>}</div>)}</div>
            </div>
            <div className="admin-panel">
              <h2>Usage by user</h2>
              <div className="admin-table">{metrics.users.map((user) => <div className="admin-row" key={user.user_id}><span><strong>{user.email}</strong><small>{user.runs} runs · {money(user.estimated_cost_usd)}</small></span><b>{compactNumber(user.total_tokens)}</b></div>)}{metrics.users.length === 0 ? <p className="admin-empty">No usage in this period.</p> : null}</div>
            </div>
            <div className="admin-panel">
              <h2>Access requests</h2>
              <div className="admin-table">{data.accessRequests.filter((item) => item.status === "pending").map((item) => <div className="admin-row" key={item.id}><span><strong>{item.email}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span><div><button aria-label="Approve access" type="button" onClick={() => void act(() => resolveAccess(item.id, "approved"), "Access approved.")}><Check /></button><button aria-label="Deny access" type="button" onClick={() => void act(() => resolveAccess(item.id, "denied"), "Access denied.")}><X /></button></div></div>)}{data.accessRequests.every((item) => item.status !== "pending") ? <p className="admin-empty">No pending requests.</p> : null}</div>
            </div>
            <div className="admin-panel">
              <h2>Models and providers</h2>
              <div className="admin-table">{metrics.models.map((model) => <div className="admin-row" key={`${model.provider}:${model.model}`}><span><strong>{model.model}</strong><small>{model.provider} · {model.attempts} attempts · {model.average_latency_ms ? `${model.average_latency_ms} ms avg` : "no latency"}</small></span><span className="admin-row-metric"><b>{compactNumber(model.total_tokens)}</b><small>{money(model.estimated_cost_usd)}</small></span></div>)}{metrics.models.length === 0 ? <p className="admin-empty">No provider activity in this period.</p> : null}</div>
            </div>
            <div className="admin-panel admin-wide">
              <h2>Allowance requests</h2>
              <div className="admin-table">{data.quotaRequests.filter((item) => item.status === "pending").map((item) => <div className="admin-row" key={item.id}><span><strong>{item.email} · +{item.requested_units}</strong><small>{item.reason}</small></span><div><button aria-label="Approve allowance" type="button" onClick={() => void act(() => resolveQuota(item.id, "approved", item.requested_units), "Allowance granted.")}><Check /></button><button aria-label="Deny allowance" type="button" onClick={() => void act(() => resolveQuota(item.id, "denied"), "Allowance request denied.")}><X /></button></div></div>)}{data.quotaRequests.every((item) => item.status !== "pending") ? <p className="admin-empty">No pending allowance requests.</p> : null}</div>
            </div>
          </section>
        </>
      ) : <div className="admin-loading">Reading operational records...</div>}
    </main>
  );
}
