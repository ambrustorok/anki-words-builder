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

export class ApiError extends Error {
  status: number;
  code?: string;
  data?: any;

  constructor(message: string, status: number, code?: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
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
  if (!response.ok) {
    let detail = response.statusText;
    let code: string | undefined;
    let data: any | undefined;
    try {
      const json = await response.json();
      detail = json.detail || json.message || detail;
      code = json.code;
      data = json.data;
    } catch (err) {
      // ignore parse errors
    }
    throw new ApiError(detail, response.status, code, data);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export { API_BASE_URL, apiFetch };
