export type MessageRole = "user" | "assistant";
export type MessageState = "complete" | "streaming" | "failed";
export type ConversationTitleState = "pending" | "generated";
export type AgentActivityKind = "thinking" | "tool" | "composing" | "connecting";

export interface AgentActivity {
  kind: AgentActivityKind;
  label: string;
  tool?: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  state: MessageState;
  reveal?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  titleState: ConversationTitleState;
  pinned: boolean;
  messages: ChatMessage[];
  updatedAt: string;
  terminated: boolean;
  activity?: AgentActivity;
}

export interface Suggestion {
  id: string;
  prompt: string;
  meta: string;
  icon: "orbit" | "signal" | "archive" | "build";
}

export interface RunEvent {
  event_id: number;
  run_id: string;
  type: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface CreateRunPayload {
  message: string;
  conversation_id: string;
  message_id: string;
  display_name?: string;
  history: Array<Pick<ChatMessage, "id" | "role" | "content">>;
  mode: "auto";
}

export interface CreateRunResponse {
  run_id: string;
  event_url: string;
  cancel_url: string;
}
