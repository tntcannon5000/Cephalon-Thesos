import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { Conversation } from "./types";
import {
  createConversationBranch,
  isConversationPersistable,
  useConversationStore,
} from "./storage";

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

  it("creates an independent branch through a completed assistant response", () => {
    const source: Conversation = {
      id: "source",
      title: "Damage calculation",
      titleState: "generated",
      pinned: true,
      updatedAt: "2026-08-16T10:00:00.000Z",
      terminated: false,
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "First question",
          createdAt: "2026-08-16T09:00:00.000Z",
          state: "complete",
        },
        {
          id: "assistant-1",
          role: "assistant",
          content: "First answer.",
          createdAt: "2026-08-16T09:00:01.000Z",
          state: "complete",
        },
        {
          id: "user-2",
          role: "user",
          content: "Later question",
          createdAt: "2026-08-16T09:01:00.000Z",
          state: "complete",
        },
      ],
    };
    const ids = ["branch", "copy-user", "copy-assistant"];
    const branch = createConversationBranch(
      source,
      "assistant-1",
      () => ids.shift() ?? "unexpected",
      "2026-08-16T11:00:00.000Z",
    );

    expect(branch?.id).toBe("branch");
    expect(branch?.messages.map((message) => message.id)).toEqual([
      "copy-user",
      "copy-assistant",
    ]);
    expect(branch?.messages.map((message) => message.content)).toEqual([
      "First question",
      "First answer.",
    ]);
    expect(branch?.pinned).toBe(false);
    expect(source.messages).toHaveLength(3);
  });

  it("refuses to branch a terminated conversation", () => {
    const source: Conversation = {
      id: "terminated",
      title: "Closed",
      titleState: "generated",
      pinned: false,
      updatedAt: "2026-08-16T10:00:00.000Z",
      terminated: true,
      messages: [
        {
          id: "assistant-1",
          role: "assistant",
          content: "Earlier answer.",
          createdAt: "2026-08-16T09:00:00.000Z",
          state: "complete",
        },
      ],
    };

    expect(createConversationBranch(source, "assistant-1")).toBeNull();
  });

  it("persists a stopped conversation after pre-response cancellation", () => {
    const conversation: Conversation = {
      id: "stopped",
      title: "Cancelled request",
      titleState: "pending",
      pinned: false,
      updatedAt: "2026-08-16T10:00:00.000Z",
      terminated: false,
      activity: { kind: "stopped", label: "Stopped" },
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "Stop this request",
          createdAt: "2026-08-16T10:00:00.000Z",
          state: "complete",
        },
      ],
    };

    expect(isConversationPersistable(conversation)).toBe(true);
    expect(
      isConversationPersistable({
        ...conversation,
        activity: { kind: "thinking", label: "Thinking" },
      }),
    ).toBe(false);
  });
});
