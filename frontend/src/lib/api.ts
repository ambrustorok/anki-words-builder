const defaultApiUrl = (() => {
  if (typeof window === "undefined") {
    return "http://localhost:8100/api";
  }
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8100/api`;
})();

const API_BASE_URL = import.meta.env.VITE_API_URL ?? defaultApiUrl;

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface FetchOptions extends RequestInit {
  method?: HttpMethod;
  json?: unknown;
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
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch (err) {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export { API_BASE_URL, apiFetch };
