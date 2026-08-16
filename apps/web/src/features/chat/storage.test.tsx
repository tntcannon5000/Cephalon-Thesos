import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useConversationStore } from "./storage";

describe("useConversationStore", () => {
  beforeEach(() => localStorage.clear());

  it("normalizes legacy chats and persists pin and delete operations", () => {
    localStorage.setItem(
      "veris.conversations.v1",
      JSON.stringify([
        {
          id: "legacy",
          title: "Legacy chat",
          messages: [
            {
              id: "answer-1",
              role: "assistant",
              content: "Already revealed.",
              createdAt: "2026-08-15T18:00:00.000Z",
              state: "complete",
              reveal: true,
            },
          ],
          updatedAt: "2026-08-15T18:00:00.000Z",
          terminated: false,
        },
      ]),
    );
    const { result } = renderHook(() => useConversationStore());

    expect(localStorage.getItem("thesos.conversations.v1")).not.toBeNull();
    expect(localStorage.getItem("veris.conversations.v1")).toBeNull();
    expect(result.current.conversations[0]?.pinned).toBe(false);
    expect(result.current.conversations[0]?.titleState).toBe("generated");
    expect(result.current.conversations[0]?.messages[0]?.reveal).toBe(false);
    act(() => result.current.toggleConversationPinned("legacy"));
    expect(result.current.conversations[0]?.pinned).toBe(true);

    act(() => result.current.deleteConversation("legacy"));
    expect(result.current.conversations).toHaveLength(0);
  });
});
