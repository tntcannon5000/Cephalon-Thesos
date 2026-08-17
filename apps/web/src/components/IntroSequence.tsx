import { ArrowRight, SignIn, UserPlus } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { normalizeDisplayName } from "../features/identity/useUserIdentity";

const WELCOME =
  "Welcome, Tenno. I am Thesos. Ask me anything and I will search the Origin System archives to answer you.";

interface IntroSequenceProps {
  mode?: "auth" | "name";
  onComplete?: (displayName?: string) => void;
  onLogin?: () => void;
  onRegister?: () => void;
  skipTyping?: boolean;
}

export function IntroSequence({
  mode = "name",
  onComplete,
  onLogin,
  onRegister,
  skipTyping = false,
}: IntroSequenceProps) {
  const reducedMotion = useReducedMotion();
  const revealImmediately = Boolean(reducedMotion) || skipTyping;
  const [visible, setVisible] = useState(revealImmediately);
  const [characters, setCharacters] = useState(revealImmediately ? WELCOME.length : 0);
  const [displayName, setDisplayName] = useState("");
  const [nameInvalid, setNameInvalid] = useState(false);
  const sequenceComplete = visible && characters >= WELCOME.length;

  useEffect(() => {
    if (revealImmediately) return;
    const revealTimer = window.setTimeout(() => setVisible(true), 680);
    return () => window.clearTimeout(revealTimer);
  }, [revealImmediately]);

  useEffect(() => {
    if (!visible || reducedMotion || characters >= WELCOME.length) return;
    const timer = window.setTimeout(() => setCharacters((current) => current + 1), 24);
    return () => window.clearTimeout(timer);
  }, [characters, reducedMotion, visible]);

  return (
    <AnimatePresence>
      <motion.section
        className="intro-sequence"
        initial={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.65, ease: "easeInOut" }}
        aria-label="Welcome to Thesos"
      >
        <motion.div
          className="intro-copy"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: visible ? 1 : 0, y: visible ? 0 : 12 }}
          transition={{ duration: 0.7 }}
        >
          <p>
            {WELCOME.slice(0, characters)}
            {characters < WELCOME.length ? <span className="type-caret" aria-hidden="true" /> : null}
          </p>
          <AnimatePresence>
            {sequenceComplete ? (
              <motion.div
                className="intro-access"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={{ duration: reducedMotion ? 0 : 0.42 }}
              >
                <form
                  className={mode === "auth" ? "intro-auth-actions" : "intro-name-form"}
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (mode === "auth") return;
                    const normalized = normalizeDisplayName(displayName);
                    if (!normalized) {
                      setNameInvalid(true);
                      return;
                    }
                    onComplete?.(normalized);
                  }}
                >
                  {mode === "auth" ? (
                    <>
                      <span>Continue into the private alpha</span>
                      <div>
                        <button type="button" onClick={onLogin}>
                          <SignIn size={17} weight="thin" /> Log in
                        </button>
                        <button className="is-primary" type="button" onClick={onRegister}>
                          <UserPlus size={17} weight="thin" /> Register
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <label htmlFor="intro-display-name">How should I address you?</label>
                      <div className="intro-name-field">
                        <input
                          id="intro-display-name"
                          value={displayName}
                          maxLength={32}
                          autoComplete="nickname"
                          autoFocus
                          aria-invalid={nameInvalid}
                          onChange={(event) => {
                            setDisplayName(event.target.value);
                            setNameInvalid(false);
                          }}
                        />
                        <button type="submit" aria-label="Enter the Archives" disabled={!displayName.trim()}>
                          <ArrowRight size={18} weight="thin" />
                        </button>
                      </div>
                      <AnimatePresence>
                        {nameInvalid ? (
                          <motion.small initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            Use up to 32 letters, numbers, spaces, apostrophes, hyphens, or periods.
                          </motion.small>
                        ) : null}
                      </AnimatePresence>
                    </>
                  )}
                </form>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
        {mode === "name" ? (
          <button className="intro-skip" type="button" onClick={() => onComplete?.()}>
            Ask me later
          </button>
        ) : null}
      </motion.section>
    </AnimatePresence>
  );
}
