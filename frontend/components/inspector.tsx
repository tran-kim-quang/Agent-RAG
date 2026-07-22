"use client";

import { useState } from "react";
import { BookOpen, GitBranch, Network, ReceiptText } from "lucide-react";
import type { Citation, EntityNode, ReasoningStep, SystemLog } from "@/lib/types";
import { SectionLabel, StatusPill } from "./ui";

type InspectorTab = "trace" | "citations" | "entities" | "logs";

export function Inspector({
  steps,
  citations,
  entities,
  logs,
  resourceUtilization,
}: {
  steps: ReasoningStep[];
  citations: Citation[];
  entities: EntityNode[];
  logs: SystemLog[];
  resourceUtilization: string;
}) {
  const [activeTab, setActiveTab] = useState<InspectorTab>("trace");
  const tabs: Array<{ id: InspectorTab; label: string; icon: typeof GitBranch }> = [
    { id: "trace", label: "Trace", icon: GitBranch },
    { id: "citations", label: "Citations", icon: BookOpen },
    { id: "entities", label: "Entities", icon: Network },
    { id: "logs", label: "Logs", icon: ReceiptText },
  ];

  return (
    <div>
      <div className="grid grid-cols-4 border-b border-white/10">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`label-caps flex min-h-[52px] items-center justify-center gap-1 text-rag-muted transition hover:bg-rag-primaryStrong/10 hover:text-rag-text ${
              activeTab === id ? "text-rag-primary shadow-[inset_0_-2px_0_#c3c0ff]" : ""
            }`}
            type="button"
            onClick={() => setActiveTab(id)}
          >
            <Icon className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">{label}</span>
          </button>
        ))}
      </div>

      {activeTab === "trace" ? <TracePanel steps={steps} /> : null}
      {activeTab === "citations" ? <CitationsPanel citations={citations} /> : null}
      {activeTab === "entities" ? <EntitiesPanel entities={entities} /> : null}
      {activeTab === "logs" ? <LogsPanel logs={logs} resourceUtilization={resourceUtilization} /> : null}
    </div>
  );
}

function TracePanel({ steps }: { steps: ReasoningStep[] }) {
  return (
    <section className="m-4 rounded-rag-lg border border-rag-outline/40 bg-midnight-panel/80 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Reasoning Trace</h3>
          <StatusPill label={steps.length ? "active" : "idle"} tone={steps.length ? "loading" : "idle"} />
        </div>
        {!steps.length ? (
          <div className="rounded-rag border border-white/10 bg-midnight-lowest/60 p-3 text-sm leading-5 text-rag-muted">
            No active backend trace. Send a chat message, upload a document, or select a graph document to populate this panel.
          </div>
        ) : null}
        <div className="grid gap-3 border-l border-white/10 pl-5">
          {steps.map((step) => (
            <article key={step.id} className="relative rounded-rag-lg border border-rag-outline/40 bg-midnight-low/80 p-3">
              <span
                className={`absolute -left-[26px] top-3 h-2.5 w-2.5 rounded-full shadow-[0_0_10px_rgba(103,244,183,0.38)] ${
                  step.tone === "error" ? "bg-rag-error" : step.tone === "loading" ? "bg-rag-secondary" : "bg-rag-success"
                }`}
              />
              <div className="flex items-center justify-between gap-2">
                <strong className="text-xs">{step.label}</strong>
                <span className="font-mono text-[10px] uppercase text-rag-muted">{step.duration}</span>
              </div>
              <p className="mt-1 text-xs leading-5 text-rag-muted">{step.detail}</p>
            </article>
          ))}
        </div>
      </section>
  );
}

function CitationsPanel({ citations }: { citations: Citation[] }) {
  return (
    <section className="m-4 rounded-rag-lg border border-rag-outline/40 bg-midnight-panel/80 p-4">
        <SectionLabel>Source Citations</SectionLabel>
        {!citations.length ? <p className="mt-3 text-sm text-rag-muted">No backend citations are available for the current run.</p> : null}
        <div className="mt-3 grid gap-2">
          {citations.map((citation) => (
            <article key={citation.id} className="rounded-rag border border-white/10 bg-midnight-lowest/60 p-3">
              <div className="flex items-center justify-between">
                <strong className="text-xs">{citation.title}</strong>
                <span className="rounded-rag bg-rag-tertiary/10 px-1.5 font-mono text-[10px] text-rag-success">
                  {citation.score}
                </span>
              </div>
              <p className="mt-1 font-mono text-[11px] leading-4 text-rag-muted">{citation.snippet}</p>
            </article>
          ))}
        </div>
      </section>
  );
}

function EntitiesPanel({ entities }: { entities: EntityNode[] }) {
  return (
    <section className="m-4 rounded-rag-lg border border-rag-outline/40 bg-midnight-panel/80 p-4">
        <SectionLabel>Entities</SectionLabel>
        {!entities.length ? <p className="mt-3 text-sm text-rag-muted">No backend entities are available for the current selection.</p> : null}
        <div className="mt-4 grid grid-cols-2 gap-2">
          {entities.map((entity) => (
            <span
              key={entity.id}
              className={`rounded-full border px-3 py-2 text-center font-mono text-[11px] ${
                entity.kind === "focus"
                  ? "border-rag-secondary bg-rag-secondary/10 text-rag-secondary"
                  : "border-rag-outline/40 bg-midnight-high/60 text-rag-muted"
              }`}
            >
              {entity.label}
            </span>
          ))}
        </div>
      </section>
  );
}

function LogsPanel({
  logs,
  resourceUtilization,
}: {
  logs: SystemLog[];
  resourceUtilization: string;
}) {
  return (
    <section className="m-4 rounded-rag-lg border border-rag-outline/40 bg-midnight-panel/80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <SectionLabel>Logs</SectionLabel>
          <span className="font-mono text-[10px] uppercase text-rag-muted">{resourceUtilization}</span>
        </div>
        {!logs.length ? <p className="text-sm text-rag-muted">No runtime logs have been loaded for this view.</p> : null}
        <div className="grid gap-1 font-mono text-[11px] leading-5 text-rag-muted">
          {logs.map((log) => (
            <p key={`${log.time}-${log.message}`}>
              <span className="text-rag-secondary">[{log.time}]</span> <span>{log.level}:</span> {log.message}
            </p>
          ))}
        </div>
      </section>
  );
}
