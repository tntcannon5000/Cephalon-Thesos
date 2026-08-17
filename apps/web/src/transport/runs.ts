import type { CreateRunPayload, CreateRunResponse, RunEvent } from "../features/chat/types";
import { emitFrontendLog } from "../features/developer/logStore";
import { csrfToken } from "./http";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

export async function createRun(payload: CreateRunPayload): Promise<CreateRunResponse> {
  const startedAt = performance.now();
  emitFrontendLog("info", "transport.runs", "Creating agent run", {
    conversation_id: payload.conversation_id,
    history_messages: payload.history.length,
  });
  const response = await fetch("/api/v1/runs", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      ...(csrfToken() ? { "X-CSRF-Token": csrfToken() as string } : {}),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let code: string | undefined;
    try {
      const body = (await response.json()) as { detail?: { code?: string } };
      code = body.detail?.code;
    } catch {
      code = undefined;
    }
    emitFrontendLog("error", "transport.runs", "Agent run creation failed", {
      code,
      duration_ms: Math.round(performance.now() - startedAt),
      status: response.status,
    });
    throw new ApiError("Run creation failed", response.status, code);
  }
  const run = (await response.json()) as CreateRunResponse;
  emitFrontendLog("info", "transport.runs", "Agent run accepted", {
    duration_ms: Math.round(performance.now() - startedAt),
    run_id: run.run_id,
  });
  return run;
}

export function subscribeToRun(
  eventUrl: string,
  callbacks: {
    onEvent: (event: RunEvent) => void;
    onDisconnect: () => void;
  },
): () => void {
  const source = new EventSource(eventUrl, { withCredentials: true });
  let terminal = false;

  emitFrontendLog("info", "transport.events", "Opening run event stream", { event_url: eventUrl });
  source.onopen = () => {
    emitFrontendLog("info", "transport.events", "Run event stream connected", {
      event_url: eventUrl,
    });
  };

  source.onmessage = (message: MessageEvent<string>) => {
    try {
      const event = JSON.parse(message.data) as RunEvent;
      emitFrontendLog("debug", "transport.events", `Received ${event.type}`, {
        event_id: event.event_id,
        run_id: event.run_id,
      });
      callbacks.onEvent(event);
      if (
        ["run.completed", "run.failed", "run.cancelled", "conversation.terminated"].includes(
          event.type,
        )
      ) {
        terminal = true;
        source.close();
        emitFrontendLog("info", "transport.events", "Run event stream completed", {
          event_url: eventUrl,
        });
      }
    } catch (error) {
      emitFrontendLog("error", "transport.events", "Invalid run event payload", error);
    }
  };
  source.onerror = () => {
    emitFrontendLog("warning", "transport.events", "Run event stream interrupted", {
      event_url: eventUrl,
      ready_state: source.readyState,
    });
    if (!terminal && source.readyState === EventSource.CLOSED) {
      callbacks.onDisconnect();
    }
  };
  return () => {
    source.close();
    emitFrontendLog("debug", "transport.events", "Run event stream closed", {
      event_url: eventUrl,
    });
  };
}

export async function editMessage(
  conversationId: string,
  messageId: string,
  replacement: string,
): Promise<void> {
  emitFrontendLog("info", "transport.messages", "Editing conversation message", {
    conversation_id: conversationId,
    message_id: messageId,
  });
  const response = await fetch(
    `/api/v1/conversations/${conversationId}/messages/${messageId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken() ? { "X-CSRF-Token": csrfToken() as string } : {}),
      },
      body: JSON.stringify({ replacement }),
    },
  );
  if (!response.ok) {
    emitFrontendLog("error", "transport.messages", "Message edit failed", {
      status: response.status,
    });
    throw new ApiError("Message edit failed", response.status);
  }
}

export async function cancelRun(cancelUrl: string): Promise<void> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const response = await fetch(cancelUrl, {
        method: "DELETE",
        credentials: "include",
        headers: csrfToken() ? { "X-CSRF-Token": csrfToken() as string } : {},
      });
      if (response.ok || response.status === 404) {
        emitFrontendLog("info", "transport.runs", "Run cancellation confirmed", {
          attempt,
          status: response.status,
        });
        return;
      }
      lastError = new ApiError("Run cancellation failed", response.status);
    } catch (error) {
      lastError = error;
    }
    if (attempt < 2) await new Promise((resolve) => window.setTimeout(resolve, 250));
  }

  emitFrontendLog("error", "transport.runs", "Run cancellation failed", lastError);
  throw lastError instanceof Error ? lastError : new Error("Run cancellation failed");
}
