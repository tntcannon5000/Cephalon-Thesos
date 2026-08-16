import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Conversation } from "../features/chat/types";
import { ThemeProvider } from "../features/theme/ThemeProvider";
import { ConversationView } from "./ConversationView";

const conversation: Conversation = {
  id: "conversation-1",
  title: "Tenno-Made Cephalons",
  titleState: "generated",
  pinned: false,
  updatedAt: "2026-08-15T18:00:00.000Z",
  terminated: false,
  messages: [
    {
      id: "user-1",
      role: "user",
      content: "Have the Tenno made Cephalons before?",
      createdAt: "2026-08-15T18:00:00.000Z",
      state: "complete",
    },
    {
      id: "assistant-1",
      role: "assistant",
      content: "The answer belongs here.",
      createdAt: "2026-08-15T18:00:01.000Z",
      state: "complete",
    },
  ],
};

function renderConversation(
  value: Conversation,
  onEdit = vi.fn(),
  onRevealComplete = vi.fn(),
) {
  return render(
    <ThemeProvider>
      <ConversationView
        conversation={value}
        onEdit={onEdit}
        onRevealComplete={onRevealComplete}
      />
    </ThemeProvider>,
  );
}

describe("ConversationView", () => {
  it("keeps the Tenno label and actions outside the message bubble", () => {
    renderConversation(conversation);

    const userArticle = screen.getByText("TENNO").closest("article");
    const bubble = userArticle?.querySelector(".message-bubble");

    expect(bubble).not.toBeNull();
    expect(within(bubble as HTMLElement).getByText(conversation.messages[0]!.content)).toBeInTheDocument();
    expect(within(bubble as HTMLElement).queryByText("TENNO")).not.toBeInTheDocument();
    expect(bubble?.querySelector("button")).toBeNull();
  });

  it("edits and copies a user message from its external actions", async () => {
    const onEdit = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    renderConversation(conversation, onEdit);

    fireEvent.click(screen.getByRole("button", { name: "Edit this message" }));
    fireEvent.click(screen.getByRole("button", { name: "Copy this message" }));

    expect(onEdit).toHaveBeenCalledWith(conversation.messages[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(conversation.messages[0]!.content));
  });

  it("shows contextual agent activity", () => {
    renderConversation({
      ...conversation,
      activity: { kind: "tool", label: "Searching archives", tool: "archive_search" },
    });

    const activity = screen.getByRole("status", { name: "Searching archives" });
    expect(activity).toHaveClass("is-tool");
    expect(activity.querySelector(".activity-icon")).not.toBeNull();
  });

  it("reveals a streaming response one word at a time", async () => {
    const onRevealComplete = vi.fn();
    renderConversation(
      {
        ...conversation,
        messages: [
          conversation.messages[0]!,
          {
            id: "streaming-answer",
            role: "assistant",
            content: "First second third.",
            createdAt: conversation.updatedAt,
            state: "streaming",
            reveal: true,
          },
        ],
      },
      vi.fn(),
      onRevealComplete,
    );

    const response = screen.getByLabelText("First second third.");
    await waitFor(() => expect(response.querySelectorAll(".streamed-word")).toHaveLength(1));
    await waitFor(() => expect(response.querySelectorAll(".streamed-word")).toHaveLength(3));
    await waitFor(() => expect(onRevealComplete).toHaveBeenCalledWith("streaming-answer"));
  });
});
