import { ArrowLeft, Check, ShieldCheck, X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Link } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import {
  addAllowlist,
  confirmMFA,
  loadAdminData,
  resolveAccess,
  resolveQuota,
  startMFA,
  updateUserStatus,
  type AccessRequest,
  type AdminOverview,
  type AdminUser,
  type MFASetup,
  type QuotaRequest,
} from "../transport/admin";

interface AdminData {
  overview: AdminOverview;
  users: AdminUser[];
  accessRequests: AccessRequest[];
  quotaRequests: QuotaRequest[];
}

export function AdminPage() {
  const auth = useAuth();
  const [data, setData] = useState<AdminData | null>(null);
  const [mfa, setMfa] = useState<MFASetup | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [allowlistEmail, setAllowlistEmail] = useState("");
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
    if (!auth.user?.roles.includes("admin") || !auth.user.admin_mfa_enrolled) return;
    let active = true;
    void loadAdminData()
      .then((loaded) => {
        if (active) setData(loaded);
      })
      .catch(() => {
        if (active) setError("The administration archive could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, [auth.user]);

  if (auth.status === "loading") return <div className="auth-loading"><i /></div>;
  if (!auth.user?.roles.includes("admin")) {
    return <main className="admin-shell"><p>Administration access is unavailable.</p><Link to="/">Return to Thesos</Link></main>;
  }

  if (!auth.user.admin_mfa_enrolled || recoveryCodes.length > 0) {
    return (
      <main className="admin-shell mfa-shell">
        <section className="admin-panel mfa-panel">
          <ShieldCheck size={25} weight="thin" />
          <p className="speaker-mark">ADMINISTRATION</p>
          <h1>{recoveryCodes.length ? "Store your recovery codes" : "Secure administrator access"}</h1>
          {recoveryCodes.length ? (
            <>
              <p>These codes are shown once. Store them somewhere separate from your authenticator.</p>
              <div className="recovery-codes">{recoveryCodes.map((code) => <code key={code}>{code}</code>)}</div>
              <Link className="admin-primary" to="/">Return and log in again</Link>
            </>
          ) : mfa ? (
            <form className="mfa-setup" onSubmit={(event) => {
              event.preventDefault();
              void confirmMFA(mfaCode).then(setRecoveryCodes).catch(() => setError("That authentication code was not accepted."));
            }}>
              <div className="mfa-qr"><QRCodeSVG value={mfa.provisioning_uri} size={176} /></div>
              <p>Scan this with your authenticator, or enter the secret manually:</p>
              <code>{mfa.secret}</code>
              <label><span>Six-digit code</span><input required inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={8} value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></label>
              {error ? <p className="admin-error">{error}</p> : null}
              <button className="admin-primary" type="submit">Confirm MFA</button>
            </form>
          ) : (
            <>
              <p>Administrator accounts require a time-based one-time password before operational data becomes available.</p>
              <button className="admin-primary" type="button" onClick={() => void startMFA().then(setMfa).catch(() => setError("MFA setup could not be started."))}>Begin setup</button>
              {error ? <p className="admin-error">{error}</p> : null}
            </>
          )}
        </section>
      </main>
    );
  }

  const act = async (operation: () => Promise<unknown>, success: string) => {
    try {
      await operation();
      setNotice(success);
      await reload();
    } catch {
      setError("The requested administration action failed.");
    }
  };

  return (
    <main className="admin-shell">
      <header className="admin-header"><div><p>THESOS</p><h1>Private alpha operations</h1></div><Link to="/"><ArrowLeft size={16} /> Return to chat</Link></header>
      {notice ? <motion.p className="admin-notice" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{notice}</motion.p> : null}
      {error ? <p className="admin-error">{error}</p> : null}
      {data ? (
        <>
          <section className="admin-metrics">
            {[
              ["Active users", data.overview.active_users], ["Runs today", data.overview.runs_today],
              ["Active runs", data.overview.active_runs], ["Live workers", data.overview.live_workers],
              ["Tokens today", data.overview.tokens_today], ["Estimated cost", `$${data.overview.estimated_cost_usd_today}`],
            ].map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}
          </section>
          <section className="admin-grid">
            <div className="admin-panel">
              <div className="admin-panel-title"><h2>Users</h2><form onSubmit={(event: FormEvent) => { event.preventDefault(); void act(() => addAllowlist(allowlistEmail), "Address added to the allowlist."); setAllowlistEmail(""); }}><input required type="email" placeholder="Allowlist email" value={allowlistEmail} onChange={(event) => setAllowlistEmail(event.target.value)} /><button type="submit">Add</button></form></div>
              <div className="admin-table">{data.users.map((user) => <div className="admin-row" key={user.id}><span><strong>{user.email}</strong><small>{user.status} · {user.runs_today} runs today</small></span>{user.id !== auth.user?.id ? <button type="button" onClick={() => void act(() => updateUserStatus(user.id, user.status === "active" ? "suspended" : "active"), user.status === "active" ? "Account suspended." : "Account activated.")}>{user.status === "active" ? "Suspend" : "Activate"}</button> : <small>You</small>}</div>)}</div>
            </div>
            <div className="admin-panel">
              <h2>Access requests</h2>
              <div className="admin-table">{data.accessRequests.filter((item) => item.status === "pending").map((item) => <div className="admin-row" key={item.id}><span><strong>{item.email}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span><div><button aria-label="Approve access" type="button" onClick={() => void act(() => resolveAccess(item.id, "approved"), "Access approved.")}><Check /></button><button aria-label="Deny access" type="button" onClick={() => void act(() => resolveAccess(item.id, "denied"), "Access denied.")}><X /></button></div></div>)}{data.accessRequests.every((item) => item.status !== "pending") ? <p className="admin-empty">No pending requests.</p> : null}</div>
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
