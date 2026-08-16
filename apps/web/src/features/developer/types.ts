export type DeveloperLayer = "frontend" | "backend" | "ai";
export type DeveloperLevel = "debug" | "info" | "warning" | "error";

export interface DeveloperLogEntry {
  id: string;
  sequence: number;
  timestamp: string;
  layer: DeveloperLayer;
  level: DeveloperLevel;
  logger: string;
  message: string;
}

export type DeveloperConnectionState = "connecting" | "live" | "reconnecting";
