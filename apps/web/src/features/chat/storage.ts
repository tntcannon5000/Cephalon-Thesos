import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  conversationPayload,
  listConversations,
  persistConversation,
  removeConversation,
} from "../../transport/conversations";
import { emitFrontendLog } from "../developer/logStore";
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

function storageKey(userId?: string): string {
  return userId ? `thesos.conversations.v2.${userId}` : CONVERSATIONS_KEY;
}

function readConversations(key: string, includeLegacy = false): Conversation[] {
  try {
    const raw = localStorage.getItem(key) ??
      (includeLegacy ? localStorage.getItem(LEGACY_CONVERSATIONS_KEY) : null);
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

export function isConversationPersistable(conversation: Conversation): boolean {
  return (!conversation.activity || conversation.activity.kind === "stopped") &&
    conversation.messages.every((message) => message.state !== "streaming");
}

function fingerprint(conversation: Conversation): string {
  return JSON.stringify(conversationPayload(conversation));
}

export function useConversationStore(userId?: string) {
  const key = storageKey(userId);
  const cloudEnabled = Boolean(userId);
  const [conversations, setConversations] = useState<Conversation[]>(() =>
    readConversations(key, !userId),
  );
  const [activeId, setActiveId] = useState<string | null>(() =>
    readConversations(key, !userId)[0]?.id ?? null,
  );
  const [hydrated, setHydrated] = useState(!cloudEnabled);
  const fingerprints = useRef(new Map<string, string>());

  useEffect(() => {
    if (!cloudEnabled) return;
    let active = true;
    const cached = readConversations(key);
    const legacy = readConversations(CONVERSATIONS_KEY, true);
    void listConversations()
      .then(async (remote) => {
        if (!active) return;
        let resolved = remote;
        const localFallback = cached.length > 0 ? cached : legacy;
        if (remote.length === 0 && localFallback.length > 0) {
          resolved = await Promise.all(
            localFallback
              .filter(isConversationPersistable)
              .map((conversation) => persistConversation(conversation)),
          );
          localStorage.removeItem(CONVERSATIONS_KEY);
          localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
        }
        resolved.forEach((conversation) =>
          fingerprints.current.set(conversation.id, fingerprint(conversation)),
        );
        setConversations(resolved);
        setActiveId((current) =>
          current && resolved.some((conversation) => conversation.id === current)
            ? current
            : (resolved[0]?.id ?? null),
        );
        setHydrated(true);
      })
      .catch((error) => {
        if (!active) return;
        emitFrontendLog("warning", "transport.conversations", "Using cached conversations", error);
        setConversations(cached);
        setActiveId(cached[0]?.id ?? null);
        setHydrated(true);
      });
    return () => {
      active = false;
    };
  }, [cloudEnabled, key]);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(key, JSON.stringify(conversations));
    if (!cloudEnabled) {
      localStorage.removeItem(LEGACY_CONVERSATIONS_KEY);
      localStorage.removeItem("veris.sample-mode");
      return;
    }
    const pending = conversations.filter((conversation) => {
      if (!isConversationPersistable(conversation)) return false;
      return fingerprints.current.get(conversation.id) !== fingerprint(conversation);
    });
    if (pending.length === 0) return;
    const timer = window.setTimeout(() => {
      for (const conversation of pending) {
        const expected = fingerprint(conversation);
        void persistConversation(conversation)
          .then(() => fingerprints.current.set(conversation.id, expected))
          .catch((error) =>
            emitFrontendLog("error", "transport.conversations", "Conversation sync failed", error),
          );
      }
    }, 650);
    return () => window.clearTimeout(timer);
  }, [cloudEnabled, conversations, hydrated, key]);

  const updateConversations = useCallback(
    (updater: (current: Conversation[]) => Conversation[]) => setConversations(updater),
    [],
  );

  const upsertConversation = useCallback((conversation: Conversation) => {
    updateConversations((current) => {
      const rest = current.filter((item) => item.id !== conversation.id);
      return [conversation, ...rest].sort(
        (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt),
      );
    });
    setActiveId(conversation.id);
  }, [updateConversations]);

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

  const deleteConversation = useCallback((id: string) => {
    updateConversations((current) => current.filter((conversation) => conversation.id !== id));
    fingerprints.current.delete(id);
    setActiveId((current) => (current === id ? null : current));
    if (cloudEnabled) {
      void removeConversation(id).catch((error) =>
        emitFrontendLog("error", "transport.conversations", "Conversation deletion failed", error),
      );
    }
  }, [cloudEnabled, updateConversations]);

  const toggleConversationPinned = useCallback((id: string) => {
    updateConversations((current) =>
      current.map((conversation) =>
        conversation.id === id
          ? { ...conversation, pinned: !conversation.pinned, updatedAt: new Date().toISOString() }
          : conversation,
      ),
    );
  }, [updateConversations]);

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
    hydrated,
    setActiveId,
    toggleConversationPinned,
    updateConversation,
    upsertConversation,
  };
}
