import type { ChatMessage, Conversation } from "../features/chat/types";
import { emitFrontendLog } from "../features/developer/logStore";
import { apiFetch } from "./http";

interface StoredMessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  state: "complete" | "streaming" | "failed";
  created_at: string;
}

interface ConversationResponse {
  id: string;
  title: string;
  title_state: "pending" | "generated";
  pinned: boolean;
  terminated: boolean;
  revision: number;
  updated_at: string;
  messages: StoredMessageResponse[];
}

function fromResponse(value: ConversationResponse): Conversation {
  return {
    id: value.id,
    title: value.title,
    titleState: value.title_state,
    pinned: value.pinned,
    terminated: value.terminated,
    updatedAt: value.updated_at,
    messages: value.messages.map((message): ChatMessage => ({
      id: message.id,
      role: message.role,
      content: message.content,
      state: message.state,
      createdAt: message.created_at,
      reveal: false,
    })),
  };
}

export function conversationPayload(conversation: Conversation) {
  return {
    title: conversation.title,
    title_state: conversation.titleState,
    pinned: conversation.pinned,
    terminated: conversation.terminated,
    updated_at: conversation.updatedAt,
    messages: conversation.messages
      .filter((message) => message.state !== "streaming" && message.content.trim())
      .map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        state: message.state,
        created_at: message.createdAt,
      })),
  };
}

export async function listConversations(): Promise<Conversation[]> {
  const values = await apiFetch<ConversationResponse[]>("/api/v1/conversations");
  return values.map(fromResponse);
}

export async function persistConversation(conversation: Conversation): Promise<Conversation> {
  const saved = await apiFetch<ConversationResponse>(`/api/v1/conversations/${conversation.id}`, {
    method: "PUT",
    body: JSON.stringify(conversationPayload(conversation)),
  });
  emitFrontendLog("debug", "transport.conversations", "Conversation synchronized", {
    conversation_id: conversation.id,
    revision: saved.revision,
  });
  return fromResponse(saved);
}

export async function removeConversation(conversationId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/conversations/${conversationId}`, { method: "DELETE" });
  emitFrontendLog("info", "transport.conversations", "Conversation deleted", {
    conversation_id: conversationId,
  });
}
