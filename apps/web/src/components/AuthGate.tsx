import { ArrowRight, EnvelopeSimple, Key, ShieldCheck } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useState, type FormEvent } from "react";

import { useAuth } from "../features/auth/AuthContext";
import { HttpError } from "../transport/http";
import { ThesosBrand } from "./ThesosBrand";
import { TurnstileWidget } from "./TurnstileWidget";

type Mode = "login" | "register" | "request" | "forgot" | "resend";

function errorMessage(error: unknown): string {
  if (error instanceof HttpError) {
    if (error.code === "invalid_credentials") return "Those credentials were not accepted.";
    if (error.code === "rate_limited") return "Too many attempts. Please wait before trying again.";
    if (error.code === "terms_version_changed") return "The terms changed. Please submit again.";
    if (error.status === 422) return "Please check the fields and try again.";
  }
  return "The Archive link could not complete that request.";
}

export function AuthGate() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const receiveTurnstileToken = useCallback((token: string | null) => {
    setTurnstileToken(token);
  }, []);

  const selectMode = (next: Mode) => {
    setMode(next);
    setNotice(null);
    setError(null);
    setPassword("");
    setConfirmation("");
    setMfaCode("");
    setMfaRequired(false);
    setTurnstileToken(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setNotice(null);
    setError(null);
    try {
      if (mode === "login") {
        await auth.login(email, password, mfaCode);
        return;
      }
      if (mode === "register") {
        if (password !== confirmation) {
          setError("The passwords do not match.");
          return;
        }
        setNotice(await auth.register(email, password, confirmation));
      } else if (mode === "request") {
        setNotice(await auth.requestAccess(email, turnstileToken ?? undefined));
      } else if (mode === "resend") {
        setNotice(await auth.resendVerification(email));
      } else {
        setNotice(await auth.forgotPassword(email));
      }
    } catch (caught) {
      if (caught instanceof HttpError && caught.code === "mfa_required") {
        setMfaRequired(true);
        setError("Enter your administrator authentication code.");
      } else {
        setError(errorMessage(caught));
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="auth-shell">
      <ThesosBrand intro={false} />
      <motion.section
        className="auth-gate"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.48 }}
      >
        <div className="auth-heading">
          <span className="auth-sigil"><ShieldCheck size={18} weight="thin" /></span>
          <p>PRIVATE ALPHA</p>
          <h1>Enter the Archives</h1>
          <small>Thesos is currently available to approved Tenno.</small>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Account access">
          <button type="button" className={mode === "login" ? "is-active" : ""} onClick={() => selectMode("login")}>Log in</button>
          <button type="button" className={mode === "register" ? "is-active" : ""} onClick={() => selectMode("register")}>Register</button>
        </div>

        <form className="auth-form" onSubmit={(event) => void submit(event)}>
          <label>
            <span>Email</span>
            <div className="auth-field"><EnvelopeSimple size={17} weight="thin" /><input required type="email" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} /></div>
          </label>
          {mode === "login" || mode === "register" ? (
            <label>
              <span>Password</span>
              <div className="auth-field"><Key size={17} weight="thin" /><input required type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 15 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /></div>
              {mode === "register" ? <small>Use at least 15 characters.</small> : null}
            </label>
          ) : null}
          {mode === "register" ? (
            <label>
              <span>Confirm password</span>
              <div className="auth-field"><Key size={17} weight="thin" /><input required type="password" autoComplete="new-password" minLength={15} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div>
            </label>
          ) : null}
          {mode === "login" && mfaRequired ? (
            <label>
              <span>Authentication code</span>
              <div className="auth-field"><ShieldCheck size={17} weight="thin" /><input required inputMode="numeric" autoComplete="one-time-code" maxLength={32} value={mfaCode} onChange={(event) => setMfaCode(event.target.value)} /></div>
            </label>
          ) : null}
          {mode === "register" ? <p className="auth-consent">Creating an account confirms acceptance of the <a href="/terms">Terms</a> and <a href="/privacy">Privacy Notice</a>.</p> : null}
          {mode === "request" && auth.config.turnstile_site_key ? (
            <TurnstileWidget
              siteKey={auth.config.turnstile_site_key}
              onToken={receiveTurnstileToken}
            />
          ) : null}
          <AnimatePresence mode="wait">
            {notice ? <motion.p className="auth-notice" initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={notice}>{notice}</motion.p> : null}
            {error ? <motion.p className="auth-error" role="alert" initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={error}>{error}</motion.p> : null}
          </AnimatePresence>
          <button
            className="auth-submit"
            type="submit"
            disabled={pending || (mode === "request" && Boolean(auth.config.turnstile_site_key) && !turnstileToken)}
          >
            <span>{pending ? "Opening link" : mode === "login" ? "Enter" : mode === "register" ? "Create account" : mode === "request" ? "Request access" : mode === "resend" ? "Send verification link" : "Send reset link"}</span>
            <ArrowRight size={18} weight="thin" />
          </button>
        </form>

        <div className="auth-secondary">
          {mode === "login" ? <button type="button" onClick={() => selectMode("forgot")}>Forgot password?</button> : null}
          {mode === "register" ? <button type="button" onClick={() => selectMode("resend")}>Resend verification</button> : null}
          {mode !== "request" ? <button type="button" onClick={() => selectMode("request")}>Not approved yet? Request access</button> : <button type="button" onClick={() => selectMode("login")}>Return to login</button>}
          {mode === "resend" || mode === "forgot" ? <button type="button" onClick={() => selectMode("login")}>Return to login</button> : null}
        </div>
      </motion.section>
      <p className="auth-legal">Unofficial. Not affiliated with Digital Extremes.</p>
    </main>
  );
}
