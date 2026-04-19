export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080";

// --- Domain types ---------------------------------------------------------

export interface NormalizedCard {
  qty: number;
  name: string;
  scryfall_id: string | null;
}

export interface NormalizedDeck {
  main: NormalizedCard[];
  side: NormalizedCard[];
}

export interface DeckResult {
  normalized: NormalizedDeck;
  // Backend also returns raw/parsed/timings/traceId but the UI doesn't need
  // them typed strictly yet.
}

export type JobState = "queued" | "processing" | "completed" | "failed";

export interface JobStatusPending {
  state: "queued" | "processing";
  progress?: number;
}

export interface JobStatusCompleted {
  state: "completed";
  result: DeckResult;
}

export interface JobStatusFailed {
  state: "failed";
  error?: { message?: string; code?: string };
}

export type JobStatus =
  | JobStatusPending
  | JobStatusCompleted
  | JobStatusFailed;

export interface ExportResponse {
  text: string;
  format: string;
}

export interface UploadResponse {
  jobId: string;
}

// --- Error type -----------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// --- HTTP helper ----------------------------------------------------------

async function request<T>(
  path: string,
  init: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body);
  }
  return (await res.json()) as T;
}

// --- API surface ----------------------------------------------------------

export async function upload(file: File, signal?: AbortSignal): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  const json = await request<UploadResponse>("/api/ocr/upload", {
    method: "POST",
    body: fd,
    signal,
  });
  return json.jobId;
}

export async function getStatus(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobStatus> {
  return request<JobStatus>(`/api/ocr/status/${jobId}`, {
    cache: "no-store",
    signal,
  });
}

export async function exportDeck(
  target: string,
  deck: NormalizedDeck,
  signal?: AbortSignal,
): Promise<ExportResponse> {
  const res = await fetch(`${API_BASE}/api/export/${target}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(deck),
    signal,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body);
  }
  const text = await res.text();
  return { text, format: target };
}
