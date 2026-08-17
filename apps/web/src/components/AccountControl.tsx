import { SignOut, UserCircle } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useOptionalAuth } from "../features/auth/AuthContext";
import { apiFetch } from "../transport/http";

export function AccountControl() {
  const auth = useOptionalAuth();
  const [open, setOpen] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [requestedUnits, setRequestedUnits] = useState(10);
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [replacementPassword, setReplacementPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  if (!auth) return null;
  const { logout, user } = auth;

  const submitRequest = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await apiFetch("/api/v1/quota-requests", {
        method: "POST",
        body: JSON.stringify({ requested_units: requestedUnits, reason }),
      });
      setNotice("Request sent for review.");
      setRequesting(false);
      setReason("");
    } catch {
      setNotice("A request is already pending, or could not be sent.");
    }
  };
  const submitPassword = async (event: FormEvent) => {
    event.preventDefault();
    if (replacementPassword !== passwordConfirmation) {
      setNotice("The replacement passwords do not match.");
      return;
    }
    try {
      setNotice(
        await auth.changePassword(
          currentPassword,
          replacementPassword,
          passwordConfirmation,
        ),
      );
      setChangingPassword(false);
      setCurrentPassword("");
      setReplacementPassword("");
      setPasswordConfirmation("");
    } catch {
      setNotice("The password could not be changed. Check your current password and try again.");
    }
  };
  if (!user) return null;

  return (
    <div className="account-control">
      <button className="account-trigger" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <UserCircle size={17} weight="thin" />
        <span>{user.preferences.display_name || user.email.split("@")[0]}</span>
        <small>{user.allowance.remaining}/{user.allowance.limit}</small>
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div className="account-menu" initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}>
            <p>{user.email}</p>
            <div><span>Archive requests today</span><strong>{user.allowance.used} / {user.allowance.limit}</strong></div>
            {requesting ? (
              <form className="allowance-form" onSubmit={(event) => void submitRequest(event)}>
                <label>Additional requests<input type="number" min={1} max={100} value={requestedUnits} onChange={(event) => setRequestedUnits(event.target.valueAsNumber)} /></label>
                <label>Reason<textarea required minLength={10} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                <button type="submit">Send request</button>
                <button type="button" onClick={() => setRequesting(false)}>Cancel</button>
              </form>
            ) : <button type="button" onClick={() => { setRequesting(true); setChangingPassword(false); }}>Request more allowance</button>}
            {changingPassword ? (
              <form className="allowance-form" onSubmit={(event) => void submitPassword(event)}>
                <label>Current password<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
                <label>New password<input required type="password" autoComplete="new-password" minLength={15} maxLength={128} value={replacementPassword} onChange={(event) => setReplacementPassword(event.target.value)} /></label>
                <label>Confirm password<input required type="password" autoComplete="new-password" minLength={15} maxLength={128} value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} /></label>
                <button type="submit">Change password</button>
                <button type="button" onClick={() => setChangingPassword(false)}>Cancel</button>
              </form>
            ) : <button type="button" onClick={() => { setChangingPassword(true); setRequesting(false); }}>Change password</button>}
            {notice ? <small className="account-notice">{notice}</small> : null}
            {user.roles.includes("admin") ? <Link to="/admin">Administration</Link> : null}
            <button type="button" onClick={() => void logout()}><SignOut size={16} weight="thin" /> Log out</button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
