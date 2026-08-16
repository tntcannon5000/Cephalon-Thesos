import { type PropsWithChildren, useCallback, useLayoutEffect, useMemo, useState } from "react";

import { ThemeContext } from "./ThemeContext";
import {
  DEFAULT_THEME_ID,
  isThemeId,
  type ThemeDefinition,
  type ThemeId,
  themes,
} from "./themes";

const THEME_KEY = "thesos.theme.v1";

function storedTheme(): ThemeId {
  const saved = localStorage.getItem(THEME_KEY);
  return isThemeId(saved) ? saved : DEFAULT_THEME_ID;
}

function applyTheme(theme: ThemeDefinition) {
  const root = document.documentElement;
  const { palette } = theme;
  const properties: Record<string, string> = {
    "--background": palette.background,
    "--surface": palette.surface,
    "--surface-solid": palette.surfaceSolid,
    "--surface-raised": palette.surfaceRaised,
    "--surface-hover": palette.surfaceHover,
    "--sidebar": palette.sidebar,
    "--header": palette.header,
    "--line": palette.line,
    "--line-strong": palette.lineStrong,
    "--text": palette.text,
    "--text-soft": palette.textSoft,
    "--muted": palette.muted,
    "--muted-dim": palette.mutedDim,
    "--accent": palette.accent,
    "--assistant": palette.assistant,
    "--accent-dim": palette.accentDim,
    "--secondary": palette.secondary,
    "--danger": palette.danger,
    "--user-bubble": palette.userBubble,
    "--focus-inset": palette.focusInset,
    "--selection-text": palette.selectionText,
    "--scrim": palette.scrim,
    "--shadow": palette.shadow,
    "--edge-duration": theme.motion.edgeDuration,
  };

  Object.entries(properties).forEach(([property, value]) => root.style.setProperty(property, value));
  root.dataset.theme = theme.id;
  root.dataset.activityMotion = theme.motion.activity;
  root.dataset.edgeMotion = theme.motion.edge;
  root.dataset.colorScheme = theme.colorScheme;
  root.style.colorScheme = theme.colorScheme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme.palette.background);
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [themeId, setThemeIdState] = useState<ThemeId>(storedTheme);
  const theme = useMemo(
    () => themes.find((candidate) => candidate.id === themeId) ?? themes[0],
    [themeId],
  );

  useLayoutEffect(() => {
    if (!theme) return;
    applyTheme(theme);
    localStorage.setItem(THEME_KEY, theme.id);
  }, [theme]);

  const setThemeId = useCallback((nextThemeId: ThemeId) => {
    setThemeIdState(nextThemeId);
  }, []);

  if (!theme) return children;

  return (
    <ThemeContext.Provider value={{ theme, themeId, setThemeId }}>
      {children}
    </ThemeContext.Provider>
  );
}
