"use client";

import { useEffect, useMemo, useState, type ChangeEvent, type CSSProperties, type DragEvent } from "react";
import { CheckCircle2, CloudUpload, FileText, Loader2, RefreshCw, Search, TriangleAlert, X } from "lucide-react";
import {
  getGraphDocument,
  getUploadStatus,
  listGraphDocuments,
  listUploadJobs,
  uploadDocument,
  type GraphDocument,
  type GraphDocumentSummary,
  type UploadStatus,
} from "@/lib/api/backend";
import type { DocumentRow, ReasoningStep } from "@/lib/types";
import { Panel, SectionLabel, StatusPill } from "./ui";

export function KnowledgeView({
  onLocalEvent,
}: {
  onLocalEvent: (label: string, detail: string, tone?: ReasoningStep["tone"]) => void;
}) {
  const [rows, setRows] = useState<DocumentRow[]>([]);
  const [graph, setGraph] = useState<GraphDocument | null>(null);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [statusLabel, setStatusLabel] = useState("Idle");
  const [uploadLabel, setUploadLabel] = useState("No upload yet");

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return rows;
    return rows.filter((row) => [row.name, row.type, row.status].some((value) => value.toLowerCase().includes(normalized)));
  }, [query, rows]);

  const liveSummary = useMemo(() => {
    const chunks = rows.reduce((sum, row) => sum + (row.chunkCount ?? 0), 0);
    return {
      documents: String(rows.length),
      chunks: chunks >= 1000 ? `${(chunks / 1000).toFixed(1)}k` : String(chunks),
    };
  }, [rows]);

  async function refreshGraph(sourceOverride?: string | null) {
    setStatus("loading");
    setStatusLabel("Refreshing");
    onLocalEvent("graph documents", "Loading indexed documents from Neo4j.", "loading");
    const [summaries, jobs] = await Promise.all([listGraphDocuments(), listUploadJobs()]);
    const nextRows = mergeGraphRowsAndUploadJobs(summaries, jobs);
    setRows(nextRows);

    const nextSource = sourceOverride ?? selectedSource ?? summaries[0]?.source ?? null;
    setSelectedSource(nextSource);
    if (nextSource) {
      setGraph(await getGraphDocument(nextSource));
      onLocalEvent("graph document", `Loaded graph for ${nextSource}.`, "success");
      setStatus("success");
      setStatusLabel("Visible");
    } else {
      setGraph(null);
      onLocalEvent("graph documents", "Neo4j returned no indexed documents.", "idle");
      setStatus("idle");
      setStatusLabel("No indexed docs");
    }
  }

  useEffect(() => {
    refreshGraph().catch((error: Error) => {
      setStatus("error");
      setStatusLabel("Backend error");
      setUploadLabel(error.message);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function processUpload(file: File) {
    if (!file) return;

    setStatus("loading");
    setStatusLabel("Uploading");
    setUploadLabel(`Uploading ${file.name}...`);
    onLocalEvent("upload queued", `Uploading ${file.name} and starting ingest.`, "loading");

    try {
      const accepted = await uploadDocument(file);
      const acceptedJob = { ...accepted, file_name: file.name };
      setUploadLabel(acceptedJob.message);
      onLocalEvent(acceptedJob.phase ?? acceptedJob.status, acceptedJob.message, "loading");
      setRows((current) => mergeUploadJobIntoRows(current, acceptedJob));
      if (!acceptedJob.job_id) {
        await refreshGraph();
        return;
      }

      const timer = window.setInterval(() => {
        getUploadStatus(acceptedJob.job_id as string)
          .then(async (job) => {
            setUploadLabel(`${job.phase ?? job.status}: ${job.message}`);
            onLocalEvent(job.phase ?? job.status, job.message, job.status === "completed" ? "success" : job.status === "failed" ? "error" : "loading");
            setRows((current) => mergeUploadJobIntoRows(current, job));
            if (job.processed_path) {
              await refreshGraph(job.processed_path);
            }
            if (job.status === "completed" || job.status === "failed") {
              window.clearInterval(timer);
              setStatus(job.status === "completed" ? "success" : "error");
              setStatusLabel(job.status === "completed" ? "Indexed" : "Failed");
              await refreshGraph(job.processed_path ?? undefined);
            }
          })
          .catch((error: Error) => {
            window.clearInterval(timer);
            setStatus("error");
            setStatusLabel("Upload error");
            setUploadLabel(error.message);
          });
      }, 2000);
    } catch (error) {
      setStatus("error");
      setStatusLabel("Upload error");
      setUploadLabel(error instanceof Error ? error.message : "Upload failed.");
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      await processUpload(file);
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) {
      processUpload(file).catch((error: Error) => {
        setStatus("error");
        setStatusLabel("Upload error");
        setUploadLabel(error.message);
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
        <Panel
          className="grid min-h-56 place-items-center border-dashed p-8 text-center transition hover:border-rag-secondary/70"
          onDragOver={(event: DragEvent<HTMLElement>) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <CloudUpload className="h-12 w-12 rounded-rag-lg bg-midnight-highest p-3 text-rag-primary" />
          <h2 className="mt-4 text-lg font-semibold">Drag & Drop Documents</h2>
          <p className="mt-2 max-w-lg text-sm leading-5 text-rag-muted">
            Upload PDF, DOCX, TXT, or JSON files to expand the agent&apos;s knowledge corpus.
          </p>
          <label className="label-caps focus-ring mt-5 cursor-pointer rounded-rag bg-rag-primaryStrong px-4 py-2 text-rag-primary transition hover:bg-[#6258ff]">
            <input className="sr-only" type="file" onChange={handleUpload} />
            Browse Files
          </label>
          <p className="mt-2 text-xs text-rag-muted">{uploadLabel}</p>
        </Panel>

        <Panel className="flex min-h-56 flex-col justify-between p-6">
          <div className="flex items-center justify-between gap-3">
            <SectionLabel>Corpus Metrics</SectionLabel>
            <StatusPill label={statusLabel} tone={status} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <MetricValue value={liveSummary.documents} label="Total Documents" />
            <MetricValue value={liveSummary.chunks} label="Vector Chunks" accent />
          </div>
          <button
            className="label-caps focus-ring flex min-h-9 items-center justify-center gap-2 rounded-rag bg-midnight-highest px-4 py-2 text-rag-text disabled:opacity-60"
            disabled={status === "loading"}
            type="button"
            onClick={() => refreshGraph().catch((error: Error) => setUploadLabel(error.message))}
          >
            {status === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync Graph
          </button>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Panel>
          <div className="flex flex-col gap-4 border-b border-white/10 bg-midnight-high/50 p-4 md:flex-row md:items-center md:justify-between md:px-6">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-rag-secondary" />
              <h2 className="text-lg font-semibold">Indexed Documents</h2>
            </div>
            <label className="flex h-9 w-full max-w-64 items-center gap-2 rounded-rag border border-rag-outline/40 bg-midnight-lowest px-3 text-rag-muted">
              <Search className="h-4 w-4" />
              <input
                className="w-full bg-transparent text-sm outline-none placeholder:text-rag-muted"
                placeholder="Search corpus..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </div>
          <div className="overflow-auto">
            {filteredRows.length ? (
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead className="bg-midnight-lowest/50">
                <tr className="label-caps text-rag-muted">
                  <th className="px-6 py-4 font-semibold">Document Name</th>
                  <th className="px-6 py-4 font-semibold">Type</th>
                  <th className="px-6 py-4 font-semibold">Date Added</th>
                  <th className="px-6 py-4 font-semibold">Ingest Status</th>
                  <th className="px-6 py-4 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((document) => (
                  <tr
                    key={document.id}
                    className="cursor-pointer border-t border-white/10 text-sm text-rag-muted hover:bg-rag-primaryStrong/10"
                    onClick={() => {
                      if (!document.source) return;
                      refreshGraph(document.source).catch((error: Error) => setUploadLabel(error.message));
                    }}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-rag-text">
                        <FileText className="h-4 w-4 shrink-0 text-rag-success" />
                        <strong className="max-w-72 truncate font-medium">{document.name}</strong>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="rounded-sm bg-midnight-highest px-1.5 py-0.5 text-xs">{document.type}</span>
                    </td>
                    <td className="px-6 py-4">{document.dateAdded}</td>
                    <td className="px-6 py-4">
                      <StatusLine document={document} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-1">
                        <button
                          aria-label="Refresh document"
                          className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            if (document.source) {
                              refreshGraph(document.source).catch((error: Error) => setUploadLabel(error.message));
                            } else {
                              setUploadLabel("This mock row has no backend graph source yet.");
                            }
                          }}
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                        </button>
                        <button
                          aria-label="Remove document"
                          className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-error/15 hover:text-rag-error"
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setUploadLabel("Delete endpoint is not available in backend yet.");
                          }}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            ) : (
              <div className="p-6 text-sm leading-6 text-rag-muted">
                No indexed documents were returned from Neo4j. Upload a document and wait for ingest to complete before this table is populated.
              </div>
            )}
          </div>
        </Panel>

        <GraphPreview
          graph={graph}
          zoom={zoom}
          onZoomIn={() => setZoom((value) => Math.min(1.35, value + 0.1))}
          onZoomOut={() => setZoom((value) => Math.max(0.75, value - 0.1))}
        />
      </div>
    </div>
  );
}

function mergeGraphRowsAndUploadJobs(summaries: GraphDocumentSummary[], jobs: UploadStatus[]): DocumentRow[] {
  const rowsBySource = new Map<string, DocumentRow>();
  summaries.forEach((summary) => {
    rowsBySource.set(summary.source, mapGraphSummaryToRow(summary));
  });

  jobs.forEach((job) => {
    const processedPath = job.processed_path ?? undefined;
    if (processedPath && rowsBySource.has(processedPath) && job.status === "completed") {
      const existing = rowsBySource.get(processedPath);
      if (existing) {
        rowsBySource.set(processedPath, {
          ...existing,
          status: "Indexed (Neo4j)",
          tone: "success",
          progress: undefined,
        });
      }
      return;
    }

    const row = mapUploadJobToRow(job);
    rowsBySource.set(row.id, row);
  });

  return Array.from(rowsBySource.values());
}

function mergeUploadJobIntoRows(rows: DocumentRow[], job: UploadStatus): DocumentRow[] {
  const next = rows.filter((row) => row.id !== `upload-${job.job_id}` && row.source !== job.processed_path);
  const row = mapUploadJobToRow(job);
  return [row, ...next];
}

function mapUploadJobToRow(job: UploadStatus): DocumentRow {
  const total = job.total_chunks ?? job.chunk_count ?? 0;
  const indexed = job.indexed_chunks ?? 0;
  const progress = total > 0 ? Math.round((indexed / total) * 100) : undefined;
  const fileName = job.file_name ?? job.source_name ?? job.processed_path ?? "Uploading document";
  const status = job.status === "completed"
    ? "Uploaded / Indexed"
    : job.status === "failed"
      ? "Ingest Failed"
      : `${job.phase ?? job.status}`;

  return {
    id: `upload-${job.job_id ?? fileName}`,
    source: job.processed_path ?? undefined,
    name: fileName,
    type: (fileName.split(".").pop() ?? "doc").toUpperCase(),
    dateAdded: "Current session",
    status,
    tone: job.status === "completed" ? "success" : job.status === "failed" ? "error" : "loading",
    progress,
    chunkCount: indexed,
  };
}

function MetricValue({ value, label, accent }: { value: string; label: string; accent?: boolean }) {
  return (
    <div>
      <strong className={`block text-5xl font-semibold leading-[56px] ${accent ? "text-rag-secondary" : "text-rag-primary"}`}>{value}</strong>
      <span className="text-sm text-rag-muted">{label}</span>
    </div>
  );
}

function StatusLine({ document }: { document: DocumentRow }) {
  const Icon = document.tone === "error" ? TriangleAlert : CheckCircle2;
  const color =
    document.tone === "error" ? "text-rag-error" : document.tone === "loading" ? "text-rag-secondary" : "text-rag-success";
  return (
    <span className={`inline-flex items-center gap-2 font-mono text-xs ${color}`}>
      <Icon className="h-4 w-4" />
      {document.status}
      {document.progress ? ` ${document.progress}%` : ""}
    </span>
  );
}

function GraphPreview({
  graph,
  zoom,
  onZoomIn,
  onZoomOut,
}: {
  graph: GraphDocument | null;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
}) {
  const nodes = useMemo(() => graph?.nodes ?? [], [graph?.nodes]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedNode = useMemo(() => {
    if (!nodes.length) return null;
    return nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  }, [nodes, selectedNodeId]);
  const positions = useMemo(() => {
    const base = [
      { left: 14, top: 22 },
      { left: 58, top: 18 },
      { left: 46, top: 48 },
      { left: 24, top: 68 },
      { left: 70, top: 70 },
      { left: 78, top: 42 },
    ];
    return new Map(nodes.map((node, index) => [node.id, base[index % base.length]]));
  }, [nodes]);
  return (
    <Panel className="grid min-h-[620px] grid-rows-[auto_minmax(0,1fr)_auto]">
      <div className="flex items-center justify-between border-b border-white/10 bg-midnight-high/50 p-4 md:px-6">
        <div className="flex items-center gap-2">
          <RefreshCw className="h-5 w-5 text-rag-secondary" />
          <h2 className="text-lg font-semibold">Graph Preview</h2>
        </div>
        <div className="flex gap-1">
          <button
            aria-label="Zoom out"
            className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
            type="button"
            onClick={onZoomOut}
          >
            -
          </button>
          <button
            aria-label="Zoom in"
            className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
            type="button"
            onClick={onZoomIn}
          >
            +
          </button>
        </div>
      </div>
      <div className="relative overflow-hidden bg-midnight-lowest">
        {!graph || !nodes.length ? (
          <div className="absolute inset-0 z-10 grid place-items-center p-6 text-center text-sm leading-6 text-rag-muted">
            No graph data returned from Neo4j for the selected document.
          </div>
        ) : null}
        <div
          className="absolute inset-0 origin-center transition-transform"
          style={{ transform: `scale(${zoom})` }}
        >
          <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:28px_28px]" />
          {graph?.edges.map((edge) => {
            const start = positions.get(edge.source_id);
            const end = positions.get(edge.target_id);
            if (!start || !end) return null;
            const dx = end.left - start.left;
            const dy = end.top - start.top;
            const width = Math.sqrt(dx * dx + dy * dy);
            const angle = Math.atan2(dy, dx) * (180 / Math.PI);
            return (
              <span
                key={`${edge.source_id}-${edge.target_id}`}
                className="absolute h-px origin-left bg-rag-secondary/30"
                style={{ left: `${start.left}%`, top: `${start.top}%`, width: `${width}%`, transform: `rotate(${angle}deg)` }}
              />
            );
          })}
          {nodes.map((node, index) => {
            const position = positions.get(node.id) ?? { left: 20, top: 20 };
            return (
              <GraphNode
                key={node.id}
                style={{ left: `${position.left}%`, top: `${position.top}%` }}
                active={(selectedNode?.id ?? nodes[0]?.id) === node.id}
                className={index === 0 ? "border-rag-primary bg-rag-primaryStrong/20 text-rag-primary" : "border-rag-secondary/70 bg-rag-secondary/10 text-rag-secondary"}
                label={`Chunk_${String(node.chunk_index ?? index).padStart(3, "0")}`}
                onClick={() => setSelectedNodeId(node.id)}
              />
            );
          })}
        </div>
        <div className="absolute bottom-3 left-3 rounded-rag border border-white/10 bg-midnight-base/80 p-2 font-mono text-[10px] text-rag-muted">
          <p>HAS_CHUNK</p>
          <p>NEXT_CHUNK</p>
        </div>
      </div>
      <div className="border-t border-white/10 bg-midnight-high/35 p-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <SectionLabel>Chunk Preview</SectionLabel>
          {selectedNode ? (
            <span className="rounded-rag bg-midnight-highest px-2 py-1 font-mono text-[10px] text-rag-secondary">
              Chunk_{String(selectedNode.chunk_index ?? 0).padStart(3, "0")}
            </span>
          ) : null}
        </div>
        <div className="max-h-40 overflow-auto rounded-rag border border-white/10 bg-midnight-lowest p-3 font-mono text-[11px] leading-5 text-rag-muted">
          {selectedNode?.preview || "Select a chunk node to view the preview returned by Neo4j."}
        </div>
      </div>
    </Panel>
  );
}

function GraphNode({
  label,
  className = "",
  style,
  active,
  onClick,
}: {
  label: string;
  className?: string;
  style?: CSSProperties;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`focus-ring absolute z-[1] max-w-40 rounded-rag-lg border px-3 py-2 text-left font-mono text-[10px] leading-4 transition hover:scale-[1.03] ${
        active ? "border-rag-warning bg-rag-warning/10 shadow-active" : "border-rag-outline/50 bg-midnight-highest"
      } ${className}`}
      style={style}
      type="button"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function mapGraphSummaryToRow(summary: GraphDocumentSummary): DocumentRow {
  const name = summary.name ?? summary.original_file_name ?? summary.source;
  const indexed = summary.indexed_chunks ?? 0;
  const total = summary.chunk_count ?? indexed;
  const isProcessing = total > 0 && indexed < total;

  return {
    id: summary.source,
    source: summary.source,
    name,
    type: (summary.source_type ?? name.split(".").pop() ?? "doc").toUpperCase(),
    dateAdded: summary.updated_at ? new Date(summary.updated_at).toLocaleDateString() : "Just now",
    status: isProcessing ? "Chunking..." : indexed > 0 ? "Indexed (Neo4j)" : "Queued",
    tone: isProcessing ? "loading" : indexed > 0 ? "success" : "idle",
    progress: isProcessing && total ? Math.round((indexed / total) * 100) : undefined,
    chunkCount: indexed,
  };
}
