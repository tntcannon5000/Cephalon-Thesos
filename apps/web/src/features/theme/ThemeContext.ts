import { createContext, useContext } from "react";

import type { ThemeDefinition, ThemeId } from "./themes";

export interface ThemeContextValue {
  theme: ThemeDefinition;
  themeId: ThemeId;
  setThemeId: (themeId: ThemeId) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
