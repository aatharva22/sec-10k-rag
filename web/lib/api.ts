import type { HealthResponse, QueryResponse } from "./types";

const DEFAULT_API_URL = "http://localhost:8000";

export function apiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL;
  return fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_API_URL;
}

export class ApiError extends Error {
  public readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * POST /query — ask the RAG backend a natural-language question.
 *
 * Throws ApiError with .status === 400 for an empty question, .status === 503
 * if the backend reports itself unhealthy, or no status when the network is
 * unreachable. The caller is expected to render a friendly retry surface.
 */
export async function postQuery(question: string): Promise<QueryResponse> {
  const url = `${apiBaseUrl()}/query`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch (err) {
    throw new ApiError(
      err instanceof Error ? err.message : "Network error reaching the backend.",
    );
  }

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}.`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // ignore; keep generic detail
    }
    throw new ApiError(detail, res.status);
  }

  const data = (await res.json()) as QueryResponse;
  return data;
}

/**
 * GET /health — used once at app load to surface a status dot. Never throws;
 * resolves to null on any failure so the UI can degrade gracefully.
 */
export async function getHealth(): Promise<HealthResponse | null> {
  try {
    const res = await fetch(`${apiBaseUrl()}/health`, { method: "GET" });
    if (!res.ok) return null;
    const data = (await res.json()) as HealthResponse;
    return data;
  } catch {
    return null;
  }
}
