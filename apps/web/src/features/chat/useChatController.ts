import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, cancelRun, createRun, editMessage, subscribeToRun } from "../../transport/runs";
import { useConversationStore } from "./storage";
import type {
  AgentActivity,
  AgentActivityKind,
  ChatMessage,
  Conversation,
  RunEvent,
} from "./types";

function now(): string {
  return new Date().toISOString();
}

function assistantId(userMessageId: string): string {
  return `v-${userMessageId.slice(2)}`;
}

function payloadText(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function eventActivity(event: RunEvent): AgentActivity {
  const allowedKinds: AgentActivityKind[] = ["thinking", "tool", "composing", "connecting"];
  const candidateKind = payloadText(event.payload.kind, "thinking") as AgentActivityKind;
  const kind = allowedKinds.includes(candidateKind) ? candidateKind : "thinking";
  const activity: AgentActivity = {
    kind,
    label: payloadText(event.payload.label ?? event.payload.message, "Thinking"),
  };
  if (typeof event.payload.tool === "string") activity.tool = event.payload.tool;
  return activity;
}

export function useChatController(displayName: string | null = null) {
  const store = useConversationStore();
  const [draft, setDraft] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const cleanupStream = useRef<(() => void) | null>(null);
  const cancelUrl = useRef<string | null>(null);

  useEffect(() => () => cleanupStream.current?.(), []);

  const updateFromEvent = useCallback(
    (conversationId: string, messageId: string, event: RunEvent) => {
      const eventTime = now();
      store.updateConversation(conversationId, (conversation) => {
        const messages = [...conversation.messages];
        const responseId = assistantId(messageId);
        const responseIndex = messages.findIndex((message) => message.id === responseId);

        if (event.type === "status.changed") {
          return {
            ...conversation,
            activity: eventActivity(event),
            updatedAt: eventTime,
          };
        }

        if (event.type === "answer.started" && responseIndex === -1) {
          messages.push({
            id: responseId,
            role: "assistant",
            content: "",
            createdAt: eventTime,
            state: "streaming",
            reveal: true,
          });
        }

        if (event.type === "answer.started") {
          return {
            ...conversation,
            activity: undefined,
            messages,
            updatedAt: eventTime,
          };
        }

        if (event.type === "answer.snapshot") {
          const text = payloadText(event.payload.text, "");
          if (responseIndex === -1) {
            messages.push({
              id: responseId,
              role: "assistant",
              content: text,
              createdAt: eventTime,
              state: "streaming",
              reveal: true,
            });
          } else {
            const response = messages[responseIndex];
            if (response) messages[responseIndex] = { ...response, content: text, reveal: true };
          }
        }

        if (event.type === "answer.delta") {
          const delta = payloadText(event.payload.delta, "");
          if (responseIndex === -1) {
            messages.push({
              id: responseId,
              role: "assistant",
              content: delta,
              createdAt: eventTime,
              state: "streaming",
              reveal: true,
            });
          } else {
            const response = messages[responseIndex];
            if (response) {
              messages[responseIndex] = {
                ...response,
                content: response.content + delta,
                reveal: true,
              };
            }
          }
        }

        if (event.type === "response.archive_unavailable") {
          const response = {
            id: responseId,
            role: "assistant" as const,
            content: payloadText(event.payload.text, "The Archives are silent on that inquiry."),
            createdAt: eventTime,
            state: "complete" as const,
            reveal: false,
          };
          if (responseIndex === -1) messages.push(response);
          else messages[responseIndex] = response;
        }

        if (event.type === "run.failed") {
          const response = {
            id: responseId,
            role: "assistant" as const,
            content: payloadText(
              event.payload.message,
              "The Archives could not be reached. Your message remains ready to retry.",
            ),
            createdAt: eventTime,
            state: "failed" as const,
            reveal: false,
          };
          if (responseIndex === -1) messages.push(response);
          else messages[responseIndex] = response;
        }

        if (event.type === "run.completed") {
          const finalIndex = messages.findIndex((message) => message.id === responseId);
          const response = messages[finalIndex];
          if (response) {
            messages[finalIndex] = { ...response, state: "complete" };
          }
        }

        const receivedTitle = event.type === "conversation.titled";
        const title = receivedTitle
          ? payloadText(event.payload.title, conversation.title)
          : conversation.title;

        return {
          ...conversation,
          title,
          titleState: receivedTitle ? "generated" : conversation.titleState,
          messages,
          terminated: event.type === "conversation.terminated" || conversation.terminated,
          activity: [
            "run.completed",
            "run.failed",
            "run.cancelled",
            "conversation.terminated",
          ].includes(event.type)
            ? undefined
            : conversation.activity,
          updatedAt: eventTime,
        };
      });

      if (
        ["run.completed", "run.failed", "run.cancelled", "conversation.terminated"].includes(
          event.type,
        )
      ) {
        setRunning(false);
        cancelUrl.current = null;
      }
    },
    [store],
  );

  const submit = useCallback(
    async (explicitPrompt?: string) => {
      const content = (explicitPrompt ?? draft).trim();
      if (!content || running) return;

      const existing = store.activeConversation;
      const conversationId = existing?.id ?? crypto.randomUUID();
      let priorMessages = existing?.messages ?? [];

      if (editingMessageId && existing) {
        const editIndex = existing.messages.findIndex((message) => message.id === editingMessageId);
        if (editIndex >= 0) {
          await editMessage(conversationId, editingMessageId, content);
          priorMessages = existing.messages.slice(0, editIndex);
        }
      }

      const messageId = crypto.randomUUID();
      const userMessage: ChatMessage = {
        id: messageId,
        role: "user",
        content,
        createdAt: now(),
        state: "complete",
      };
      const firstTurn = priorMessages.length === 0;
      const conversation: Conversation = {
        id: conversationId,
        title: firstTurn ? content : (existing?.title ?? content),
        titleState: firstTurn ? "pending" : (existing?.titleState ?? "generated"),
        pinned: existing?.pinned ?? false,
        messages: [...priorMessages, userMessage],
        updatedAt: now(),
        terminated: false,
        activity: { kind: "thinking", label: "Preparing" },
      };

      store.upsertConversation(conversation);
      setDraft("");
      setEditingMessageId(null);
      setRunning(true);

      try {
        const run = await createRun({
          message: content,
          conversation_id: conversationId,
          message_id: messageId,
          ...(displayName ? { display_name: displayName } : {}),
          history: priorMessages.map(({ id, role, content: priorContent }) => ({
            id,
            role,
            content: priorContent,
          })),
          mode: "auto",
        });
        cancelUrl.current = run.cancel_url;
        cleanupStream.current?.();
        cleanupStream.current = subscribeToRun(run.event_url, {
          onEvent: (event) => updateFromEvent(conversationId, messageId, event),
          onDisconnect: () => {
            store.updateConversation(conversationId, (current) => ({
              ...current,
              activity: { kind: "connecting", label: "Reconnecting" },
            }));
          },
        });
      } catch (error) {
        const terminated = error instanceof ApiError && error.code === "conversation_terminated";
        store.updateConversation(conversationId, (current) => ({
          ...current,
          terminated: terminated || current.terminated,
          activity: undefined,
          messages: terminated
            ? current.messages
            : [
                ...current.messages,
                {
                  id: assistantId(messageId),
                  role: "assistant",
                  content: "The Archive link is unavailable. Please try that request again.",
                  createdAt: now(),
                  state: "failed",
                },
              ],
        }));
        setRunning(false);
      }
    },
    [displayName, draft, editingMessageId, running, store, updateFromEvent],
  );

  const beginEdit = useCallback((message: ChatMessage) => {
    setEditingMessageId(message.id);
    setDraft(message.content);
  }, []);

  const completeReveal = useCallback(
    (messageId: string) => {
      const conversation = store.activeConversation;
      if (!conversation) return;
      store.updateConversation(conversation.id, (current) => ({
        ...current,
        messages: current.messages.map((message) =>
          message.id === messageId ? { ...message, reveal: false } : message,
        ),
      }));
    },
    [store],
  );

  const stop = useCallback(async () => {
    if (cancelUrl.current) await cancelRun(cancelUrl.current);
    cleanupStream.current?.();
    setRunning(false);
  }, []);

  const newChat = useCallback(() => {
    cleanupStream.current?.();
    setRunning(false);
    setDraft("");
    setEditingMessageId(null);
    store.setActiveId(null);
  }, [store]);

  return {
    ...store,
    beginEdit,
    completeReveal,
    draft,
    editingMessageId,
    newChat,
    running,
    setDraft,
    setEditingMessageId,
    stop,
    submit,
  };
}
