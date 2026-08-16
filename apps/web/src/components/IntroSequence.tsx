import { ArrowRight } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import { normalizeDisplayName } from "../features/identity/useUserIdentity";

const WELCOME =
  "Welcome, Tenno. I am Thesos. Ask me anything and I will search the Origin System archives to answer you.";

interface IntroSequenceProps {
  onComplete: (displayName?: string) => void;
}

export function IntroSequence({ onComplete }: IntroSequenceProps) {
  const reducedMotion = useReducedMotion();
  const [visible, setVisible] = useState(Boolean(reducedMotion));
  const [characters, setCharacters] = useState(reducedMotion ? WELCOME.length : 0);
  const [displayName, setDisplayName] = useState("");
  const [nameInvalid, setNameInvalid] = useState(false);
  const sequenceComplete = visible && characters >= WELCOME.length;

  useEffect(() => {
    if (reducedMotion) return;
    const revealTimer = window.setTimeout(() => setVisible(true), 680);
    return () => window.clearTimeout(revealTimer);
  }, [reducedMotion]);

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
                <div className="intro-auth-actions" aria-label="Account access">
                  <button type="button">Sign in</button>
                  <button type="button">Register</button>
                </div>
                <div className="intro-divider" aria-hidden="true"><i /><span>or</span><i /></div>
                <form
                  className="intro-name-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const normalized = normalizeDisplayName(displayName);
                    if (!normalized) {
                      setNameInvalid(true);
                      return;
                    }
                    onComplete(normalized);
                  }}
                >
                  <label htmlFor="intro-display-name">Enter your name</label>
                  <div className="intro-name-field">
                    <input
                      id="intro-display-name"
                      value={displayName}
                      maxLength={32}
                      autoComplete="nickname"
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
                </form>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </motion.div>
        <button className="intro-skip" type="button" onClick={() => onComplete()}>
          Enter Archives
        </button>
      </motion.section>
    </AnimatePresence>
  );
}
