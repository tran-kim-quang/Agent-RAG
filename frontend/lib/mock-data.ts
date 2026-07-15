import type {
  ChatMessage,
  Citation,
  DocumentRow,
  EntityNode,
  Metric,
  ModelConfig,
  NavItem,
  ReasoningStep,
  SystemLog,
} from "./types";

export const primaryNavigation: NavItem[] = [
  { id: "chat", label: "Chat Dashboard", icon: "message" },
  { id: "knowledge", label: "Knowledge Base", icon: "database" },
  { id: "status", label: "Agent Status", icon: "barChart" },
];

export const utilityNavigation: NavItem[] = [
  { id: "settings", label: "Settings", icon: "settings" },
  { id: "support", label: "Support", icon: "help" },
];

export const chatMessages: ChatMessage[] = [
  {
    id: "q1",
    role: "user",
    content: "How does Neo4j integration improve retrieval accuracy compared to standard vector stores?",
  },
  {
    id: "a1",
    role: "assistant",
    citations: ["1", "2"],
    content:
      "Integrating Neo4j improves retrieval by combining semantic similarity with graph topology. Vector search finds close chunks, then graph expansion follows relationships like NEXT_CHUNK and SIMILAR_TO to pull structurally relevant context before synthesis.",
  },
  {
    id: "a2",
    role: "assistant",
    content: "Synthesizing final response...",
  },
];

export const reasoningSteps: ReasoningStep[] = [
  {
    id: "reformulation",
    label: "Query Reformulation",
    duration: "42ms",
    detail: '"Neo4j retrieval accuracy vs vector stores"',
    tone: "success",
  },
  {
    id: "vector",
    label: "Vector Search (Neo4j)",
    duration: "128ms",
    detail: "Retrieved 15 nodes. Top score: 0.89",
    tone: "success",
  },
  {
    id: "expansion",
    label: "Graph Expansion",
    duration: "315ms",
    detail: "Expanded via NEXT_CHUNK. Added 22 nodes.",
    tone: "success",
  },
  {
    id: "rerank",
    label: "Reranking & Synthesis",
    duration: "active",
    detail: "Evaluating node relevance and cross-referencing page rank.",
    tone: "loading",
  },
];

export const citations: Citation[] = [
  {
    id: "1",
    title: "Graph retrieval architecture",
    score: "0.89",
    snippet: "Vector candidates are expanded through graph links before final reranking.",
  },
  {
    id: "2",
    title: "Neo4j chunk topology",
    score: "0.84",
    snippet: "NEXT_CHUNK and SIMILAR_TO relationships preserve document adjacency.",
  },
];

export const entityNodes: EntityNode[] = [
  { id: "neo4j", label: "Neo4j", kind: "focus" },
  { id: "vectors", label: "Vector Embeddings", kind: "related" },
  { id: "chunks", label: "Document Chunks", kind: "source" },
  { id: "llm", label: "LLM Synthesis", kind: "related" },
];

export const documents: DocumentRow[] = [
  {
    id: "q3-report",
    name: "Q3_Financial_Report_Final.pdf",
    type: "PDF",
    dateAdded: "Just now",
    status: "Chunking...",
    tone: "loading",
    progress: 45,
  },
  {
    id: "onboarding",
    name: "Engineering_Onboarding_v2.docx",
    type: "DOCX",
    dateAdded: "Oct 24, 2023",
    status: "Indexed (Neo4j)",
    tone: "success",
  },
  {
    id: "api-docs",
    name: "API_Documentation_v1.md",
    type: "MD",
    dateAdded: "Oct 22, 2023",
    status: "Indexed (Neo4j)",
    tone: "success",
  },
  {
    id: "archive",
    name: "Corrupted_Archive.zip",
    type: "ZIP",
    dateAdded: "Oct 20, 2023",
    status: "OCR Failed",
    tone: "error",
  },
];

export const corpusSummary = {
  documents: "142",
  chunks: "8.4k",
};

export const systemMetrics: Metric[] = [
  {
    label: "FastAPI",
    value: "Online",
    detail: "Uptime 99.98% · p95 45ms",
    icon: "zap",
    tone: "tertiary",
  },
  {
    label: "Neo4j Graph",
    value: "Connected",
    detail: "1.2M nodes · 4.8M relationships",
    icon: "network",
    tone: "secondary",
  },
  {
    label: "Token Consumption",
    value: "12k",
    detail: "Today",
    icon: "activity",
    tone: "primary",
  },
  {
    label: "Embedding Job Queue",
    value: "12",
    detail: "Pending document chunks",
    icon: "shield",
    tone: "warning",
  },
];

export const modelConfigs: ModelConfig[] = [
  { key: "LLM_MODEL_NAME", value: "llama3:8b-instruct", provider: "Local (Ollama)" },
  { key: "VISION_MODEL_NAME", value: "llava:7b", provider: "Local (Ollama)" },
  { key: "EMBEDDING_MODEL", value: "mxbai-embed-large", provider: "Local (Ollama)" },
  { key: "GRAPH_EXTRACTION_MODEL", value: "gpt-4-turbo", provider: "OpenAI API" },
];

export const systemLogs: SystemLog[] = [
  { time: "14:02:11", level: "INFO", message: "Indexed 452 new chunks into Neo4j." },
  { time: "14:02:15", level: "SUCCESS", message: "Vector embeddings generated." },
  { time: "14:02:45", level: "REQ", message: "User query received (ID: 982a)." },
  { time: "14:02:46", level: "TRACE", message: "Querying Ollama [llama3]." },
  { time: "14:02:48", level: "SUCCESS", message: "Response generated in 2.1s." },
  { time: "14:05:00", level: "WARN", message: "Embedding queue length > 10." },
];

export const commandCenter = {
  brand: "Agent-RAG",
  subtitle: "AI Command Center",
  activeStatus: "All Systems Operational",
  contextWindow: "14k/128k tokens",
  resourceUtilization: "GPU Mem: 4.2GB · Nominal",
  projectSource: "https://github.com/tran-kim-quang/Agent-RAG",
  sourceSummary:
    "Repository extraction is available as reference text in Stitch and is represented here as a future corpus source.",
};
