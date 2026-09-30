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
  return typeof message === "string" ? message : null;
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  const contentType = response.headers.get("content-type") ?? "";
  const rawBody = await response.text();
  let payload: unknown;

  if (!rawBody.trim()) {
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
