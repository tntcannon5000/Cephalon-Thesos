import { useCallback, useState } from "react";

export const DEFAULT_SIDEBAR_WIDTH = 254;
export const MIN_SIDEBAR_WIDTH = 210;
export const MAX_SIDEBAR_WIDTH = 380;

const SIDEBAR_WIDTH_KEY = "thesos.sidebar-width.v1";

export function clampSidebarWidth(width: number): number {
  return Math.round(Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, width)));
}

function storedSidebarWidth(): number {
  const stored = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
  return Number.isFinite(stored) && stored > 0
    ? clampSidebarWidth(stored)
    : DEFAULT_SIDEBAR_WIDTH;
}

export function useSidebarWidth() {
  const [sidebarWidth, setSidebarWidthState] = useState(storedSidebarWidth);

  const setSidebarWidth = useCallback((width: number) => {
    const nextWidth = clampSidebarWidth(width);
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(nextWidth));
    setSidebarWidthState(nextWidth);
  }, []);

  const resetSidebarWidth = useCallback(() => {
    localStorage.removeItem(SIDEBAR_WIDTH_KEY);
    setSidebarWidthState(DEFAULT_SIDEBAR_WIDTH);
  }, []);

  return { resetSidebarWidth, setSidebarWidth, sidebarWidth };
}
