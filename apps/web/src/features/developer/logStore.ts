import type { DeveloperLevel, DeveloperLogEntry } from "./types";

type ConsoleMethod = "debug" | "error" | "info" | "log" | "warn";
type LogSubscriber = (entry: DeveloperLogEntry) => void;

interface DeveloperLogStoreState {
  entries: DeveloperLogEntry[];
  installed: boolean;
  original: Record<ConsoleMethod, (...args: unknown[]) => void>;
  sequence: number;
  subscribers: Set<LogSubscriber>;
}

interface DeveloperGlobal {
  __VERIS_DEVELOPER_LOG_STORE__?: DeveloperLogStoreState;
}

const MAX_FRONTEND_LOGS = 400;
const developerGlobal = globalThis as typeof globalThis & DeveloperGlobal;

function createState(): DeveloperLogStoreState {
  return {
    entries: [],
    installed: false,
    original: {
      debug: console.debug.bind(console),
      error: console.error.bind(console),
      info: console.info.bind(console),
      log: console.log.bind(console),
      warn: console.warn.bind(console),
    },
    sequence: 0,
    subscribers: new Set(),
  };
}

const state = (developerGlobal.__VERIS_DEVELOPER_LOG_STORE__ ??= createState());

function serialize(value: unknown): string {
  if (typeof value === "string") return value;
  if (value instanceof Error) return value.stack ?? `${value.name}: ${value.message}`;
  if (typeof value === "bigint") return `${String(value)}n`;

  const seen = new WeakSet<object>();
  try {
    const serialized = JSON.stringify(value, (_key, nested: unknown) => {
      if (typeof nested === "bigint") return `${String(nested)}n`;
      if (typeof nested === "object" && nested !== null) {
        if (seen.has(nested)) return "[Circular]";
        seen.add(nested);
      }
      return nested;
    });
    return serialized ?? String(value);
  } catch {
    return String(value);
  }
}

function append(level: DeveloperLevel, logger: string, message: string): DeveloperLogEntry {
  state.sequence += 1;
  const entry: DeveloperLogEntry = {
    id: `frontend-${state.sequence}`,
    sequence: state.sequence,
    timestamp: new Date().toISOString(),
    layer: "frontend",
    level,
    logger,
    message,
  };
  state.entries = [...state.entries.slice(-(MAX_FRONTEND_LOGS - 1)), entry];
  state.subscribers.forEach((subscriber) => subscriber(entry));
  return entry;
}

function levelFor(method: ConsoleMethod): DeveloperLevel {
  if (method === "error") return "error";
  if (method === "warn") return "warning";
  if (method === "debug") return "debug";
  return "info";
}

export function installFrontendConsoleCapture(): void {
  if (state.installed || !import.meta.env.DEV) return;
  state.installed = true;

  const methods: ConsoleMethod[] = ["debug", "error", "info", "log", "warn"];
  methods.forEach((method) => {
    console[method] = (...args: unknown[]) => {
      append(levelFor(method), "console", args.map(serialize).join(" "));
      state.original[method](...args);
    };
  });

  window.addEventListener("error", (event) => {
    append(
      "error",
      "window.error",
      event.error instanceof Error ? serialize(event.error) : event.message,
    );
  });
  window.addEventListener("unhandledrejection", (event) => {
    append("error", "window.unhandledrejection", serialize(event.reason));
  });
}

export function emitFrontendLog(
  level: DeveloperLevel,
  logger: string,
  message: string,
  details?: unknown,
): void {
  if (!import.meta.env.DEV) return;
  const content = details === undefined ? message : `${message} ${serialize(details)}`;
  append(level, logger, content);

  const method: ConsoleMethod = level === "warning" ? "warn" : level;
  state.original[method](`[${logger}] ${message}`, ...(details === undefined ? [] : [details]));
}

export function getFrontendLogs(): DeveloperLogEntry[] {
  return [...state.entries];
}

export function subscribeToFrontendLogs(subscriber: LogSubscriber): () => void {
  state.subscribers.add(subscriber);
  return () => state.subscribers.delete(subscriber);
}

export function clearFrontendLogs(): void {
  state.entries = [];
}
