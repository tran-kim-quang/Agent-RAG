import { useEffect, useState } from "react";
import { Activity, Database, Loader2, Server, Terminal, UploadCloud } from "lucide-react";
import { getRuntimeStatus, type RuntimeConfig, type RuntimeLog, type RuntimeMetric } from "@/lib/api/backend";
import { iconMap } from "@/lib/icons";
import type { Metric } from "@/lib/types";
import { Panel, SectionLabel, StatusPill } from "./ui";

const metricToneClasses: Record<Metric["tone"], string> = {
  primary: "text-rag-primary",
  secondary: "text-rag-secondary",
  tertiary: "text-rag-success",
  warning: "text-rag-warning",
};

export function StatusView({
  activeStatus,
}: {
  activeStatus: string;
}) {
  const [metrics, setMetrics] = useState<RuntimeMetric[]>([]);
  const [configs, setConfigs] = useState<RuntimeConfig[]>([]);
  const [logs, setLogs] = useState<RuntimeLog[]>([]);
  const [status, setStatus] = useState(activeStatus);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getRuntimeStatus()
      .then((payload) => {
        setMetrics(payload.metrics);
        setConfigs(payload.configs);
        setLogs(payload.logs);
        setStatus(payload.status === "ok" ? "Backend Online" : `Backend ${payload.status}`);
      })
      .catch((error: Error) => {
        setStatus("Backend Offline");
        setMetrics([]);
        setConfigs([]);
        setLogs([{ time: "", level: "ERROR", message: error.message }]);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <Panel className="p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <SectionLabel>System Performance</SectionLabel>
            <h2 className="mt-1 text-2xl font-semibold">Real-time metrics and model configurations</h2>
          </div>
          <StatusPill label={status} tone={status.toLowerCase().includes("offline") ? "error" : loading ? "loading" : "success"} />
        </div>
      </Panel>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.length ? metrics.map((metric) => {
          const Icon = getMetricIcon(metric.label);
          const tone = normalizeTone(metric.tone);
          return (
            <Panel key={metric.label} className="p-5">
              <div className="mb-5 flex items-center justify-between">
                <span className="label-caps text-rag-muted">{metric.label}</span>
                <Icon className={`h-5 w-5 ${metricToneClasses[tone]}`} />
              </div>
              <strong className={`block text-3xl font-semibold ${metricToneClasses[tone]}`}>{metric.value}</strong>
              <p className="mt-2 text-sm text-rag-muted">{metric.detail}</p>
            </Panel>
          );
        }) : (
          <Panel className="p-5 md:col-span-2 xl:col-span-4">
            <div className="flex items-center gap-2 text-rag-muted">
              {loading ? <Loader2 className="h-4 w-4 animate-spin text-rag-secondary" /> : null}
              <span>{loading ? "Loading backend runtime status..." : "No backend runtime metrics are available."}</span>
            </div>
          </Panel>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.85fr)]">
        <Panel>
          <div className="border-b border-white/10 bg-midnight-high/50 p-5">
            <SectionLabel>Active Model Configuration</SectionLabel>
          </div>
          <div className="overflow-auto">
            <table className="w-full min-w-[680px] border-collapse text-left">
              <thead className="bg-midnight-lowest/50">
                <tr className="label-caps text-rag-muted">
                  <th className="px-6 py-4 font-semibold">Environment Variable</th>
                  <th className="px-6 py-4 font-semibold">Active Value</th>
                  <th className="px-6 py-4 font-semibold">Provider</th>
                </tr>
              </thead>
              <tbody>
                {configs.length ? configs.map((config) => (
                  <tr key={config.key} className="border-t border-white/10 text-sm text-rag-muted">
                    <td className="px-6 py-4 font-mono text-rag-secondary">{config.key}</td>
                    <td className="px-6 py-4 text-rag-text">{config.value}</td>
                    <td className="px-6 py-4">{config.provider}</td>
                  </tr>
                )) : (
                  <tr className="border-t border-white/10 text-sm text-rag-muted">
                    <td className="px-6 py-4" colSpan={3}>Runtime config endpoint returned no values.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <Terminal className="h-5 w-5 text-rag-secondary" />
            <SectionLabel>Runtime Logs</SectionLabel>
          </div>
          <div className="grid gap-2 font-mono text-xs leading-5 text-rag-muted">
            {logs.map((log) => (
              <p key={`${log.time}-${log.level}-${log.message}`}>
                <span className="text-rag-secondary">[{log.time}]</span>{" "}
                <span className={log.level === "WARN" ? "text-rag-warning" : log.level === "SUCCESS" ? "text-rag-success" : "text-rag-muted"}>
                  {log.level}:
                </span>{" "}
                {log.message}
              </p>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function normalizeTone(tone: string): Metric["tone"] {
  return tone === "secondary" || tone === "tertiary" || tone === "warning" ? tone : "primary";
}

function getMetricIcon(label: string) {
  const normalized = label.toLowerCase();
  if (normalized.includes("fastapi")) return Server;
  if (normalized.includes("neo4j") || normalized.includes("graph")) return Database;
  if (normalized.includes("queue") || normalized.includes("ingest")) return UploadCloud;
  if (normalized.includes("corpus")) return iconMap.database;
  return Activity;
}
