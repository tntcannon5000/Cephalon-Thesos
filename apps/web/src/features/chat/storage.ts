import { useCallback, useEffect, useMemo, useState } from "react";

import type { AgentActivity, Conversation } from "./types";

const CONVERSATIONS_KEY = "thesos.conversations.v1";
const LEGACY_CONVERSATIONS_KEY = "veris.conversations.v1";

export function createConversationBranch(
  source: Conversation,
  throughMessageId: string,
  idFactory: () => string = () => crypto.randomUUID(),
  createdAt = new Date().toISOString(),
): Conversation | null {
  if (source.terminated) return null;
  const branchIndex = source.messages.findIndex(
    (message) =>
      message.id === throughMessageId &&
      message.role === "assistant" &&
      message.state === "complete",
  );
  if (branchIndex < 0) return null;

  return {
    id: idFactory(),
    title: source.title,
    titleState: source.titleState,
    pinned: false,
    messages: source.messages.slice(0, branchIndex + 1).map((message) => ({
      ...message,
      id: idFactory(),
      state: "complete",
      reveal: false,
    })),
    updatedAt: createdAt,
    terminated: false,
  };
}

function readConversations(): Conversation[] {
  try {
    const raw =
      localStorage.getItem(CONVERSATIONS_KEY) ?? localStorage.getItem(LEGACY_CONVERSATIONS_KEY);
    if (!raw) return [];
    const stored = JSON.parse(raw) as Array<
      Omit<Conversation, "activity"> & { activity?: AgentActivity | string }
    >;
    return stored.map((conversation) => {
      const activity =
        typeof conversation.activity === "string"
          ? { kind: "thinking" as const, label: conversation.activity }
          : conversation.activity;
      return {
        ...conversation,
        activity,
        messages: conversation.messages.map((message) => ({ ...message, reveal: false })),
        pinned: conversation.pinned === true,
        titleState: conversation.titleState === "pending" ? "pending" : "generated",
      };
    });
  } catch {
    return [];
  }
}

export function useConversationStore() {
  const [conversations, setConversations] = useState<Conversation[]>(readConversations);
  const [activeId, setActiveId] = useState<string | null>(
    () => readConversations()[0]?.id ?? null,
  );

  useEffect(() => {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
    localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
    localStorage.removeItem("veris.sample-mode");
  }, [conversations]);

  const updateConversations = useCallback(
    (updater: (current: Conversation[]) => Conversation[]) => {
      setConversations(updater);
    },
    [],
  );

  const upsertConversation = useCallback(
    (conversation: Conversation) => {
      updateConversations((current) => {
        const rest = current.filter((item) => item.id !== conversation.id);
        return [conversation, ...rest].sort(
          (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt),
        );
      });
      setActiveId(conversation.id);
    },
    [setActiveId, updateConversations],
  );

  const updateConversation = useCallback(
    (id: string, updater: (conversation: Conversation) => Conversation) => {
      updateConversations((current) =>
        current
          .map((conversation) => (conversation.id === id ? updater(conversation) : conversation))
          .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt)),
      );
    },
    [updateConversations],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      updateConversations((current) => current.filter((conversation) => conversation.id !== id));
      if (activeId === id) setActiveId(null);
    },
    [activeId, setActiveId, updateConversations],
  );

  const toggleConversationPinned = useCallback(
    (id: string) => {
      updateConversations((current) =>
        current.map((conversation) =>
          conversation.id === id
            ? { ...conversation, pinned: !conversation.pinned }
            : conversation,
        ),
      );
    },
    [updateConversations],
  );

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [activeId, conversations],
  );

  return {
    activeConversation,
    activeId,
    conversations,
    deleteConversation,
    conversationCount: conversations.length,
    setActiveId,
    toggleConversationPinned,
    updateConversation,
    upsertConversation,
  };
}
