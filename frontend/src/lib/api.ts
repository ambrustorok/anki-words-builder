const defaultApiUrl = (() => {
  if (typeof window === "undefined") {
    return "http://localhost:8100/api";
  }
  const origin = window.location.origin.replace(/\/$/, "");
  return `${origin}/api`;
})();

const API_BASE_URL = import.meta.env.VITE_API_URL ?? defaultApiUrl;

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface FetchOptions extends RequestInit {
  method?: HttpMethod;
  json?: unknown;
}

class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body
  });
  const text = await response.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const payload = typeof data === "object" && data !== null ? (data as Record<string, unknown>) : undefined;
    const detail = (payload?.detail as string) || (payload?.message as string) || response.statusText;
    throw new ApiError(detail, response.status, data);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (data as T) ?? (undefined as T);
}

export { API_BASE_URL, ApiError, apiFetch };
