import { AuthenticationExpiredError, AuthSessionManager } from "./auth-session";

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
  owner_id: string | null;
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

export type ChatStreamEvent =
  | { type: "ready"; run_id: string }
  | { type: "start"; attempt: string }
  | { type: "token"; content: string }
  | { type: "status"; status: string; message: string }
  | { type: "done"; answer?: string | null }
  | { type: "error"; message: string }
  | { type: "heartbeat" };

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "");

async function readResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : { detail: await response.text() };
  if (!response.ok) throw new Error(payload.detail ?? payload.message ?? `Request failed with ${response.status}`);
  return payload as T;
}

async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${await authSession.accessToken()}`);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retry) {
    await refreshSession();
    return apiFetch(path, init, false);
  }
  if (response.status === 401) {
    authSession.clear();
    throw new AuthenticationExpiredError();
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
  return authSession.accept(payload);
}

export function login(email: string, password: string) {
  return submitCredentials("/auth/login", email, password);
}

export function register(email: string, password: string) {
  return submitCredentials("/auth/register", email, password);
}

async function requestRefresh(): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, { method: "POST", credentials: "include" });
  if (response.status === 401) throw new AuthenticationExpiredError();
  return readResponse<AuthResponse>(response);
}

const authSession = new AuthSessionManager<AuthResponse>(requestRefresh);

export function refreshSession(): Promise<AuthResponse> {
  return authSession.refresh();
}

export function subscribeAuthSession(listener: (session: AuthResponse | null) => void): () => void {
  return authSession.subscribe(listener);
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
  } finally {
    authSession.clear();
  }
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

export async function connectChatRunStream(
  runId: string,
  onEvent: (event: ChatStreamEvent) => void,
  onDisconnect: () => void,
): Promise<WebSocket> {
  const token = await authSession.accessToken();
  const websocketBase = API_BASE_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  const socket = new WebSocket(`${websocketBase}/chat/${encodeURIComponent(runId)}/stream`);
  let finished = false;
  socket.onopen = () => socket.send(JSON.stringify({ type: "authenticate", token }));
  socket.onmessage = (message) => {
    const event = JSON.parse(String(message.data)) as ChatStreamEvent;
    if (event.type === "done" || event.type === "error") finished = true;
    onEvent(event);
  };
  socket.onerror = () => {
    if (!finished) onDisconnect();
  };
  socket.onclose = () => {
    if (!finished) onDisconnect();
  };
  return socket;
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

export async function retryUploadJob(jobId: string): Promise<UploadStatus> {
  return readResponse<UploadStatus>(await apiFetch(`/documents/upload/${encodeURIComponent(jobId)}/retry`, { method: "POST" }));
}

export async function listUploadJobs(limit = 20): Promise<UploadStatus[]> {
  const payload = await readResponse<{ jobs: UploadStatus[] }>(await apiFetch(`/documents/uploads?limit=${limit}`, { cache: "no-store" }));
  return payload.jobs;
}

export async function listGraphDocuments(limit = 20): Promise<GraphDocumentSummary[]> {
  const payload = await readResponse<{ documents: GraphDocumentSummary[] }>(await apiFetch(`/graph/documents?limit=${limit}`, { cache: "no-store" }));
  return payload.documents;
}

export async function getGraphDocument(source: string, limitChunks = 18, ownerId?: string | null): Promise<GraphDocument> {
  const params = new URLSearchParams({ source, limit_chunks: String(limitChunks) });
  if (ownerId) params.set("owner_id", ownerId);
  return readResponse<GraphDocument>(await apiFetch(`/graph/document?${params}`, { cache: "no-store" }));
}

export async function deleteGraphDocument(source: string, ownerId?: string | null): Promise<void> {
  const params = new URLSearchParams({ source });
  if (ownerId) params.set("owner_id", ownerId);
  await readResponse<{ message: string }>(await apiFetch(`/graph/document?${params}`, { method: "DELETE" }));
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
