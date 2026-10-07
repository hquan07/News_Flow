export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getErrorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;

  const message = (payload as { message?: unknown }).message;
  if (typeof message === "string") return message;

  const error = (payload as { error?: unknown }).error;
  if (error && typeof error === "object") {
    const nestedMessage = (error as { message?: unknown }).message;
    if (typeof nestedMessage === "string") return nestedMessage;
  }
  return null;
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  const contentType = response.headers.get("content-type") ?? "";
  const rawBody = await response.text();
  let payload: unknown;

  if (!rawBody.trim()) {
    if (response.ok && response.status === 204) return undefined as T;
    throw new ApiError(
      response.ok
        ? "API returned an empty response."
        : `API request failed (HTTP ${response.status}).`,
      response.status,
      requestId,
    );
  }

  try {
    payload = JSON.parse(rawBody);
  } catch {
    const responseType = contentType.split(";")[0] || "unknown content type";
    throw new ApiError(
      `API returned a non-JSON response (HTTP ${response.status}, ${responseType}).`,
      response.status,
      requestId,
    );
  }

  if (!response.ok) {
    throw new ApiError(
      getErrorDetail(payload) ?? `API request failed (HTTP ${response.status}).`,
      response.status,
      requestId,
    );
  }

  return payload as T;
}

export async function apiFetch<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (typeof window !== "undefined" && !headers.has("Authorization")) {
    const token = localStorage.getItem("token");
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  return parseJsonResponse<T>(response);
}

export async function apiSse(
  input: RequestInfo | URL,
  init: RequestInit,
  onEvent: (event: string, data: unknown) => void,
): Promise<void> {
  const headers = new Headers(init.headers);
  if (typeof window !== "undefined" && !headers.has("Authorization")) {
    const token = localStorage.getItem("token");
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(input, { ...init, headers });
  if (!response.ok || !response.body) {
    await parseJsonResponse<never>(response);
    throw new ApiError("API stream returned no body.", response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function dispatch(frame: string) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    const raw = dataLines.join("\n");
    try { onEvent(event, JSON.parse(raw)); }
    catch { throw new ApiError("API stream returned an invalid event.", response.status); }
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    frames.forEach(dispatch);
    if (done) break;
  }
  if (buffer.trim()) dispatch(buffer);
}
