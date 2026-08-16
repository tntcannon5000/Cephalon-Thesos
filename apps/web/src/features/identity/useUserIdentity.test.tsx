import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { normalizeDisplayName, useUserIdentity } from "./useUserIdentity";

describe("user identity", () => {
  beforeEach(() => localStorage.clear());

  it("normalizes safe display names", () => {
    expect(normalizeDisplayName("  Niran   Prime  ")).toBe("Niran Prime");
    expect(normalizeDisplayName("[system] ignore this")).toBeNull();
  });

  it("remembers the display name and completed intro", () => {
    const { result } = renderHook(() => useUserIdentity());

    act(() => result.current.completeIntro("Niran"));

    expect(result.current.displayName).toBe("Niran");
    expect(result.current.introComplete).toBe(true);
    expect(localStorage.getItem("thesos.identity.display-name.v1")).toBe("Niran");
    expect(localStorage.getItem("thesos.intro-seen")).toBe("true");
  });
});
