import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_SIDEBAR_WIDTH,
  MAX_SIDEBAR_WIDTH,
  MIN_SIDEBAR_WIDTH,
  useSidebarWidth,
} from "./useSidebarWidth";

describe("sidebar width", () => {
  beforeEach(() => localStorage.clear());

  it("persists and clamps resize values", () => {
    const { result } = renderHook(() => useSidebarWidth());
    expect(result.current.sidebarWidth).toBe(DEFAULT_SIDEBAR_WIDTH);

    act(() => result.current.setSidebarWidth(999));
    expect(result.current.sidebarWidth).toBe(MAX_SIDEBAR_WIDTH);

    act(() => result.current.setSidebarWidth(12));
    expect(result.current.sidebarWidth).toBe(MIN_SIDEBAR_WIDTH);
  });
});
