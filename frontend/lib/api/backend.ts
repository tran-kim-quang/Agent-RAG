export type AgentRunEvent = {
  timestamp: string;
  phase: string;
  message: string;
  details: Record<string, unknown>;
};

export type User = {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type ChatRun = {
  run_id: string;
  chat_session_id: string;
  status: string;
  message: string;
  answer: string | null;
  error: string | null;
  events: AgentRunEvent[];
};

export type ChatSession = {
  run_id: string;
  user_id: string;
  title: string;
  status: string;
  answer: string | null;
  error: string | null;
  messages: Array<{ id: string; role: "user" | "assistant"; content: string; created_at: string }>;
  created_at: string;
  updated_at: string;
};

export type UploadStatus = {
  job_id: string | null;
  user_id?: string | null;
  status: string;
  message: string;
  phase: string | null;
  raw_path?: string | null;
  processed_path?: string | null;
  metadata_path?: string | null;
  raw_object_key?: string | null;
  processed_object_key?: string | null;
  metadata_object_key?: string | null;
  progress: number;
  attempt_count: number;
  chunk_count?: number | null;
  source_name?: string | null;
  error?: string | null;
  file_name?: string | null;
  indexed_chunks?: number | null;
  total_chunks?: number | null;
};

export type GraphDocumentSummary = {
  source: string;
  name: string | null;
  raw_source: string | null;
  original_file_name: string | null;
  source_type: string | null;
  chunk_count: number | null;
  indexed_chunks: number | null;
  updated_at: string | null;
};

export type GraphNode = { id: string; chunk_index: number | null; preview: string | null };
export type GraphEdge = { source_id: string; target_id: string };
export type GraphDocument = { document: GraphDocumentSummary | null; nodes: GraphNode[]; edges: GraphEdge[] };
export type Health = { status: string };
export type RuntimeMetric = { label: string; value: string; detail: string; tone: "primary" | "secondary" | "tertiary" | "warning" | string };
export type RuntimeConfig = { key: string; value: string; provider: string };
export type RuntimeLog = { time: string; level: string; message: string };
export type RuntimeStatus = { status: string; metrics: RuntimeMetric[]; configs: RuntimeConfig[]; logs: RuntimeLog[] };

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "");
let accessToken: string | null = null;
let refreshPromise: Promise<AuthResponse> | null = null;

async function readResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : { detail: await response.text() };
  if (!response.ok) throw new Error(payload.detail ?? payload.message ?? `Request failed with ${response.status}`);
  return payload as T;
}

async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retry) {
    try {
      await refreshSession();
      return apiFetch(path, init, false);
    } catch {
      accessToken = null;
    }
  }
  return response;
}

async function submitCredentials(path: string, email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await readResponse<AuthResponse>(response);
  accessToken = payload.access_token;
  return payload;
}

export function login(email: string, password: string) {
  return submitCredentials("/auth/login", email, password);
}

export function register(email: string, password: string) {
  return submitCredentials("/auth/register", email, password);
}

export async function refreshSession(): Promise<AuthResponse> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, { method: "POST", credentials: "include" })
      .then(readResponse<AuthResponse>)
      .then((payload) => {
        accessToken = payload.access_token;
        return payload;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
  accessToken = null;
}

export async function getHealth(): Promise<Health> {
  return readResponse<Health>(await fetch(`${API_BASE_URL}/health`, { cache: "no-store" }));
}

export async function createChatRun(message: string, chatSessionId?: string | null): Promise<ChatRun> {
  return readResponse<ChatRun>(await apiFetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, chat_session_id: chatSessionId ?? null }),
  }));
}

export async function getChatRun(runId: string): Promise<ChatRun> {
  return readResponse<ChatRun>(await apiFetch(`/chat/${encodeURIComponent(runId)}`, { cache: "no-store" }));
}

export async function listChatSessions(limit = 20): Promise<ChatSession[]> {
  const payload = await readResponse<{ sessions: ChatSession[] }>(await apiFetch(`/chat/sessions?limit=${limit}`, { cache: "no-store" }));
  return payload.sessions;
}

export async function uploadDocument(file: File): Promise<UploadStatus> {
  const body = new FormData();
  body.append("file", file);
  return readResponse<UploadStatus>(await apiFetch("/documents/upload", { method: "POST", body }));
}

export async function getUploadStatus(jobId: string): Promise<UploadStatus> {
  return readResponse<UploadStatus>(await apiFetch(`/documents/upload/${encodeURIComponent(jobId)}`, { cache: "no-store" }));
}

export async function listUploadJobs(limit = 20): Promise<UploadStatus[]> {
  const payload = await readResponse<{ jobs: UploadStatus[] }>(await apiFetch(`/documents/uploads?limit=${limit}`, { cache: "no-store" }));
  return payload.jobs;
}

export async function listGraphDocuments(limit = 20): Promise<GraphDocumentSummary[]> {
  const payload = await readResponse<{ documents: GraphDocumentSummary[] }>(await apiFetch(`/graph/documents?limit=${limit}`, { cache: "no-store" }));
  return payload.documents;
}

export async function getGraphDocument(source: string, limitChunks = 18): Promise<GraphDocument> {
  const params = new URLSearchParams({ source, limit_chunks: String(limitChunks) });
  return readResponse<GraphDocument>(await apiFetch(`/graph/document?${params}`, { cache: "no-store" }));
}

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  return readResponse<RuntimeStatus>(await apiFetch("/status", { cache: "no-store" }));
}

export async function listAdminUsers(): Promise<User[]> {
  return (await readResponse<{ users: User[] }>(await apiFetch("/admin/users", { cache: "no-store" }))).users;
}

export async function listAdminUploads(): Promise<UploadStatus[]> {
  return (await readResponse<{ jobs: UploadStatus[] }>(await apiFetch("/admin/uploads", { cache: "no-store" }))).jobs;
}

export async function listAdminChatSessions(): Promise<ChatSession[]> {
  return (await readResponse<{ sessions: ChatSession[] }>(await apiFetch("/admin/chat-sessions", { cache: "no-store" }))).sessions;
}
