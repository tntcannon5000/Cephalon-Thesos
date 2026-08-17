import { ArrowLeft, ArrowRight, CheckCircle } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

interface AuthActionPageProps {
  action: "verify" | "reset";
}

function fragmentToken(): string {
  const raw = window.location.hash.replace(/^#/, "");
  const params = new URLSearchParams(raw);
  return params.get("token") ?? raw;
}

export function AuthActionPage({ action }: AuthActionPageProps) {
  const auth = useAuth();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(
    action === "verify"
      ? fragmentToken()
        ? "Verifying your address..."
        : "This verification link is incomplete."
      : "Choose a replacement password.",
  );
  const [complete, setComplete] = useState(false);
  const verificationStarted = useRef(false);
  const [token] = useState(fragmentToken);

  useEffect(() => {
    if (!window.location.hash) return;
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  }, []);

  useEffect(() => {
    if (action !== "verify" || !token || verificationStarted.current) return;
    verificationStarted.current = true;
    void auth.verifyEmail(token).then((result) => {
      setMessage(result);
      setComplete(true);
    }).catch(() => setMessage("This verification link is invalid or has expired."));
  }, [action, auth, token]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirmation) {
      setMessage("The passwords do not match.");
      return;
    }
    try {
      setMessage(await auth.resetPassword(token, password, confirmation));
      setComplete(true);
    } catch {
      setMessage("This reset link is invalid or has expired.");
    }
  };

  return (
    <main className="auth-shell auth-action-shell">
      <motion.section className="auth-gate auth-action" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <CheckCircle size={24} weight="thin" />
        <p className="speaker-mark">THESOS</p>
        <h1>{action === "verify" ? "Archive access" : "Replace password"}</h1>
        <p>{message}</p>
        {action === "reset" && !complete ? (
          <form className="auth-form" onSubmit={(event) => void submit(event)}>
            <label><span>New password</span><div className="auth-field"><input required type="password" minLength={15} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /></div></label>
            <label><span>Confirm password</span><div className="auth-field"><input required type="password" minLength={15} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div></label>
            <button className="auth-submit" type="submit"><span>Replace password</span><ArrowRight size={18} /></button>
          </form>
        ) : null}
        <Link className="auth-return" to="/"><ArrowLeft size={16} /> Return to login</Link>
      </motion.section>
    </main>
  );
}
