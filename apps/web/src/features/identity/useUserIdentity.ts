import { useCallback, useState } from "react";

const DISPLAY_NAME_KEY = "thesos.identity.display-name.v1";
const INTRO_KEY = "thesos.intro-seen";
const LEGACY_INTRO_KEY = "veris.intro-seen";
const DISPLAY_NAME_PATTERN = /^[\p{L}\p{N}][\p{L}\p{N} ._'-]{0,31}$/u;

export function normalizeDisplayName(value: string): string | null {
  const normalized = value.trim().replace(/\s+/g, " ");
  return DISPLAY_NAME_PATTERN.test(normalized) ? normalized : null;
}

function readDisplayName(): string | null {
  const stored = localStorage.getItem(DISPLAY_NAME_KEY);
  return stored ? normalizeDisplayName(stored) : null;
}

export function useUserIdentity() {
  const [displayName, setDisplayName] = useState<string | null>(readDisplayName);
  const [introComplete, setIntroComplete] = useState(
    () =>
      localStorage.getItem(INTRO_KEY) === "true" ||
      localStorage.getItem(LEGACY_INTRO_KEY) === "true",
  );

  const completeIntro = useCallback((candidateName?: string) => {
    const normalized = candidateName ? normalizeDisplayName(candidateName) : null;
    if (normalized) {
      localStorage.setItem(DISPLAY_NAME_KEY, normalized);
      setDisplayName(normalized);
    }
    localStorage.setItem(INTRO_KEY, "true");
    localStorage.removeItem(LEGACY_INTRO_KEY);
    setIntroComplete(true);
  }, []);

  return { completeIntro, displayName, introComplete };
}
