import { useCallback, useEffect, useState } from "react";

import {
  clearFrontendLogs,
  getFrontendLogs,
  subscribeToFrontendLogs,
} from "./logStore";
import type {
  DeveloperConnectionState,
  DeveloperLayer,
  DeveloperLevel,
  DeveloperLogEntry,
} from "./types";

const MAX_VISIBLE_LOGS = 800;

interface RemoteLogEntry {
  sequence: number;
  timestamp: string;
  layer: Exclude<DeveloperLayer, "frontend">;
  level: DeveloperLevel;
  logger: string;
  message: string;
}

function isRemoteLogEntry(value: unknown): value is RemoteLogEntry {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Partial<RemoteLogEntry>;
  return (
    typeof entry.sequence === "number" &&
    typeof entry.timestamp === "string" &&
    (entry.layer === "backend" || entry.layer === "ai") &&
    ["debug", "info", "warning", "error"].includes(entry.level ?? "") &&
    typeof entry.logger === "string" &&
    typeof entry.message === "string"
  );
}

function appendLog(current: DeveloperLogEntry[], entry: DeveloperLogEntry): DeveloperLogEntry[] {
  if (current.some((candidate) => candidate.id === entry.id)) return current;
  return [...current, entry]
    .sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    .slice(-MAX_VISIBLE_LOGS);
}

export function useDeveloperLogs(enabled: boolean) {
  const [logs, setLogs] = useState<DeveloperLogEntry[]>(() => getFrontendLogs());
  const [connection, setConnection] = useState<DeveloperConnectionState>(() =>
    typeof EventSource === "undefined" ? "reconnecting" : "connecting",
  );

  useEffect(() => {
    if (!enabled) return;

    const unsubscribe = subscribeToFrontendLogs((entry) => {
      setLogs((current) => appendLog(current, entry));
    });

    if (typeof EventSource === "undefined") {
      return unsubscribe;
    }

    let source: EventSource | null = null;
    let reconnectTimer: number | undefined;
    let lastActivity = Date.now();

    function markActivity(): void {
      lastActivity = Date.now();
      setConnection("live");
    }

    function scheduleReconnect(): void {
      if (reconnectTimer !== undefined) return;
      setConnection("reconnecting");
      source?.close();
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = undefined;
        connect();
      }, 1_200);
    }

    function connect(): void {
      source?.close();
      lastActivity = Date.now();
      const nextSource = new EventSource("/api/v1/developer/logs");
      source = nextSource;
      nextSource.onopen = markActivity;
      nextSource.addEventListener("heartbeat", markActivity);
      nextSource.onmessage = (message: MessageEvent<string>) => {
        try {
          const parsed: unknown = JSON.parse(message.data);
          if (!isRemoteLogEntry(parsed)) return;
          markActivity();
          setLogs((current) =>
            appendLog(current, {
              ...parsed,
              id: `${parsed.layer}-${parsed.sequence}`,
            }),
          );
        } catch {
          scheduleReconnect();
        }
      };
      nextSource.onerror = scheduleReconnect;
    }

    connect();
    const staleTimer = window.setInterval(() => {
      if (Date.now() - lastActivity > 12_000) {
        scheduleReconnect();
      }
    }, 3_000);

    return () => {
      unsubscribe();
      source?.close();
      window.clearInterval(staleTimer);
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
    };
  }, [enabled]);

  const clear = useCallback(() => {
    clearFrontendLogs();
    setLogs([]);
  }, []);

  return { clear, connection, logs };
}
