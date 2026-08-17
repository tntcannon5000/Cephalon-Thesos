import { createContext, useContext } from "react";

import type { AuthContextValue } from "./types";

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext);
}

export function useAuth(): AuthContextValue {
  const context = useOptionalAuth();
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
