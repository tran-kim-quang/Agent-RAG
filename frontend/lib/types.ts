export type ViewId = "chat" | "knowledge" | "status" | "admin";

export type IconKey =
  | "activity"
  | "barChart"
  | "database"
  | "help"
  | "message"
  | "network"
  | "settings"
  | "shield"
  | "zap";

export type NavItem = {
  id: ViewId | "settings" | "support";
  label: string;
  icon: IconKey;
};

export type StatusTone = "idle" | "loading" | "success" | "warning" | "error";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: string[];
  pending?: boolean;
  error?: boolean;
};

export type ReasoningStep = {
  id: string;
  label: string;
  duration: string;
  detail: string;
  tone: StatusTone;
  timestamp?: string;
};

export type Citation = {
  id: string;
  title: string;
  score: string;
  snippet: string;
};

export type EntityNode = {
  id: string;
  label: string;
  kind: "focus" | "related" | "source";
};

export type DocumentRow = {
  id: string;
  source?: string;
  name: string;
  type: string;
  dateAdded: string;
  status: string;
  tone: StatusTone;
  progress?: number;
  chunkCount?: number;
};

export type Metric = {
  label: string;
  value: string;
  detail: string;
  icon: IconKey;
  tone: "primary" | "secondary" | "tertiary" | "warning";
};

export type ModelConfig = {
  key: string;
  value: string;
  provider: string;
};

export type SystemLog = {
  time: string;
  level: "INFO" | "SUCCESS" | "REQ" | "TRACE" | "WARN";
  message: string;
};
