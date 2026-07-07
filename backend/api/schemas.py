from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message sent from the frontend")


class AgentRunEventResponse(BaseModel):
    timestamp: str
    phase: str
    message: str
    details: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    run_id: str
    status: str
    message: str
    answer: str | None = None
    error: str | None = None
    events: list[AgentRunEventResponse] = Field(default_factory=list)


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


class HealthResponse(BaseModel):
    status: str


class UploadStatusResponse(UploadResponse):
    file_name: str | None = None
    indexed_chunks: int | None = None
    total_chunks: int | None = None


class GraphDocumentSummary(BaseModel):
    source: str
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
