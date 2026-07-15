"use client";

import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import {
  listAdminChatSessions,
  listAdminUploads,
  listAdminUsers,
  type ChatSession,
  type UploadStatus,
  type User,
} from "@/lib/api/backend";
import { Panel, SectionLabel } from "./ui";

export function AdminView() {
  const [users, setUsers] = useState<User[]>([]);
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [nextUsers, nextUploads, nextSessions] = await Promise.all([
        listAdminUsers(), listAdminUploads(), listAdminChatSessions(),
      ]);
      setUsers(nextUsers);
      setUploads(nextUploads);
      setSessions(nextSessions);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load admin data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh().catch(() => undefined); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div><SectionLabel>Administration</SectionLabel><h2 className="mt-1 text-2xl font-semibold">Users and background activity</h2></div>
        <button aria-label="Refresh admin data" className="focus-ring grid h-9 w-9 place-items-center rounded-rag bg-midnight-highest text-rag-muted" onClick={() => refresh()} type="button">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </button>
      </div>
      {error ? <p className="text-sm text-rag-error">{error}</p> : null}
      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Users" value={users.length} />
        <Metric label="Upload jobs" value={uploads.length} />
        <Metric label="Chat sessions" value={sessions.length} />
      </div>
      <Panel className="overflow-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="label-caps bg-midnight-lowest/50 text-rag-muted"><tr><th className="p-4">User</th><th className="p-4">Role</th><th className="p-4">Created</th><th className="p-4">State</th></tr></thead>
          <tbody>{users.map((user) => <tr className="border-t border-white/10" key={user.id}><td className="p-4 text-rag-text">{user.email}</td><td className="p-4 text-rag-secondary">{user.role}</td><td className="p-4 text-rag-muted">{new Date(user.created_at).toLocaleString()}</td><td className="p-4 text-rag-muted">{user.is_active ? "Active" : "Disabled"}</td></tr>)}</tbody>
        </table>
      </Panel>
      <div className="grid gap-6 xl:grid-cols-2">
        <ActivityPanel title="Recent uploads" rows={uploads.map((job) => ({ id: job.job_id ?? job.file_name ?? "upload", title: job.file_name ?? "Upload", detail: `${job.status} / ${job.progress}%` }))} />
        <ActivityPanel title="Recent chats" rows={sessions.map((session) => ({ id: session.run_id, title: session.title, detail: session.status }))} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <Panel className="p-5"><SectionLabel>{label}</SectionLabel><strong className="mt-2 block text-3xl text-rag-primary">{value}</strong></Panel>;
}

function ActivityPanel({ title, rows }: { title: string; rows: Array<{ id: string; title: string; detail: string }> }) {
  return <Panel><h3 className="border-b border-white/10 p-4 font-semibold">{title}</h3><div>{rows.slice(0, 12).map((row) => <div className="flex items-center justify-between gap-4 border-t border-white/10 p-4 first:border-0" key={row.id}><span className="truncate text-sm text-rag-text">{row.title}</span><span className="label-caps shrink-0 text-rag-muted">{row.detail}</span></div>)}</div></Panel>;
}
