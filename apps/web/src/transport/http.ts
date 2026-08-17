export class HttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

function cookieValue(name: string): string | null {
  const prefix = `${name}=`;
  const value = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

export function csrfToken(): string | null {
  return cookieValue("__Host-thesos_csrf") ?? cookieValue("thesos_csrf");
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }

  const response = await fetch(path, { ...init, credentials: "include", headers });
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  let detail: unknown;
  let code: string | undefined;
  try {
    const body = (await response.json()) as { detail?: unknown };
    detail = body.detail;
    if (typeof detail === "object" && detail && "code" in detail) {
      const candidate = (detail as { code?: unknown }).code;
      if (typeof candidate === "string") code = candidate;
    }
  } catch {
    detail = undefined;
  }
  throw new HttpError(`Request failed with status ${response.status}`, response.status, code, detail);
}
