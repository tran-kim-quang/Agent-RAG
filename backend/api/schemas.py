from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=10, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message sent from the frontend")
    chat_session_id: str | None = Field(default=None, min_length=32, max_length=32)


class AgentRunEventResponse(BaseModel):
    timestamp: str
    phase: str
    message: str
    details: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    run_id: str
    chat_session_id: str
    status: str
    message: str
    answer: str | None = None
    error: str | None = None
    events: list[AgentRunEventResponse] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatSessionResponse(BaseModel):
    run_id: str
    user_id: str
    title: str
    status: str
    answer: str | None = None
    error: str | None = None
    messages: list[ChatMessageResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionResponse]


class UploadResponse(BaseModel):
    job_id: str | None = None
    status: str = "accepted"
    message: str
    phase: str | None = None
    raw_path: str | None = None
    processed_path: str | None = None
    metadata_path: str | None = None
    chunk_count: int | None = None
    source_name: str | None = None
    error: str | None = None
    raw_object_key: str | None = None
    processed_object_key: str | None = None
    metadata_object_key: str | None = None
    progress: int = 0
    attempt_count: int = 0


class HealthResponse(BaseModel):
    status: str


class UploadStatusResponse(UploadResponse):
    user_id: str | None = None
    file_name: str | None = None
    indexed_chunks: int | None = None
    total_chunks: int | None = None


class UploadJobsResponse(BaseModel):
    jobs: list[UploadStatusResponse]


class GraphDocumentSummary(BaseModel):
    source: str
    owner_id: str | None = None
    name: str | None = None
    raw_source: str | None = None
    original_file_name: str | None = None
    source_type: str | None = None
    chunk_count: int | None = None
    indexed_chunks: int | None = None
    updated_at: str | None = None


class GraphNode(BaseModel):
    id: str
    chunk_index: int | None = None
    preview: str | None = None


class GraphEdge(BaseModel):
    source_id: str
    target_id: str


class GraphDocumentResponse(BaseModel):
    document: GraphDocumentSummary | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphOverviewResponse(BaseModel):
    documents: list[GraphDocumentSummary]


class RuntimeMetric(BaseModel):
    label: str
    value: str
    detail: str
    tone: str = "primary"


class RuntimeConfig(BaseModel):
    key: str
    value: str
    provider: str


class RuntimeLog(BaseModel):
    time: str
    level: str
    message: str


class RuntimeStatusResponse(BaseModel):
    status: str
    metrics: list[RuntimeMetric]
    configs: list[RuntimeConfig]
    logs: list[RuntimeLog]


class UsersResponse(BaseModel):
    users: list[UserResponse]
