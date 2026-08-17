import { ArrowRight, ShieldCheck, ShieldWarning } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { QRCodeSVG } from "qrcode.react";

import { confirmMFA, startMFA, type MFASetup } from "../transport/admin";

interface AdminMfaControlProps {
  enrolled: boolean;
}

export function AdminMfaControl({ enrolled }: AdminMfaControlProps) {
  const [setup, setSetup] = useState<MFASetup | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const begin = async () => {
    try {
      setSetup(await startMFA());
      setError(null);
    } catch {
      setError("MFA setup could not be started.");
    }
  };

  const confirm = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setRecoveryCodes(await confirmMFA(code));
      setError(null);
    } catch {
      setError("That authentication code was not accepted.");
    }
  };

  return (
    <section className="admin-security" aria-label="Administrator security">
      <div className="admin-security-summary">
        {enrolled ? <ShieldCheck size={20} weight="thin" /> : <ShieldWarning size={20} weight="thin" />}
        <span>
          <strong>{enrolled ? "MFA enabled" : "MFA is optional"}</strong>
          <small>{enrolled ? "Administrator logins require an authenticator code." : "This administrator account currently uses password-only login."}</small>
        </span>
        {!enrolled && !setup && recoveryCodes.length === 0 ? <button type="button" onClick={() => void begin()}>Set up MFA <ArrowRight size={14} /></button> : null}
      </div>
      <AnimatePresence>
        {setup && recoveryCodes.length === 0 ? (
          <motion.form className="admin-mfa-setup" onSubmit={(event) => void confirm(event)} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
            <div className="mfa-qr"><QRCodeSVG value={setup.provisioning_uri} size={148} /></div>
            <div>
              <p>Scan this with an authenticator, or enter the secret manually.</p>
              <code>{setup.secret}</code>
              <label><span>Six-digit code</span><input required inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={8} value={code} onChange={(event) => setCode(event.target.value)} /></label>
              {error ? <p className="admin-error">{error}</p> : null}
              <button className="admin-primary" type="submit">Enable MFA</button>
            </div>
          </motion.form>
        ) : null}
        {recoveryCodes.length ? (
          <motion.div className="admin-recovery" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div><strong>Store these recovery codes now</strong><small>They are shown once. Enabling MFA ended your other sessions, so log in again after saving them.</small></div>
            <div className="recovery-codes">{recoveryCodes.map((recoveryCode) => <code key={recoveryCode}>{recoveryCode}</code>)}</div>
            <a className="admin-primary" href="/">Return to login</a>
          </motion.div>
        ) : null}
      </AnimatePresence>
      {error && !setup ? <p className="admin-error">{error}</p> : null}
    </section>
  );
}
