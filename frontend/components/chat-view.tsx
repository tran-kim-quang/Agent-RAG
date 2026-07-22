"use client";

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Bot, Loader2, Paperclip, Plus, Send, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { connectChatRunStream, createChatRun, getChatRun, getUploadStatus, listChatSessions, uploadDocument, type AgentRunEvent, type ChatSession, type ChatStreamEvent } from "@/lib/api/backend";
import { isAuthenticationExpiredError } from "@/lib/api/auth-session";
import type { ChatMessage, ReasoningStep } from "@/lib/types";
import { Panel, StatusPill } from "./ui";

export function ChatView({
  messages,
  contextWindow,
  onEvents,
  onLocalEvent,
}: {
  messages: ChatMessage[];
  contextWindow: string;
  onEvents: (events: AgentRunEvent[]) => void;
  onLocalEvent: (label: string, detail: string, tone?: ReasoningStep["tone"]) => void;
}) {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(messages);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [statusLabel, setStatusLabel] = useState("Idle");
  const [uploading, setUploading] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const completedRuns = useRef(new Set<string>());
  const stoppedRuns = useRef(new Set<string>());
  const activeRunId = useRef<string | null>(null);
  const chatPollTimer = useRef<number | null>(null);
  const chatStreamSocket = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [chatMessages]);

  useEffect(() => {
    listChatSessions().then(setSessions).catch(() => setSessions([]));
    return () => {
      if (chatPollTimer.current) window.clearInterval(chatPollTimer.current);
      chatStreamSocket.current?.close(1000, "View closed");
    };
  }, []);

  function openSession(session: ChatSession) {
    setActiveSessionId(session.run_id);
    setChatMessages(session.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      error: message.role === "assistant" && session.status === "failed",
    })));
    setStatus(session.status === "failed" ? "error" : session.status === "completed" ? "success" : "loading");
    setStatusLabel(session.status);
  }

  function startNewSession() {
    setActiveSessionId(null);
    setChatMessages([]);
    setStatus("idle");
    setStatusLabel("Idle");
    onEvents([]);
  }

  async function pollRun(runId: string) {
    const run = await getChatRun(runId);
    onEvents(run.events);
    setStatus(run.status === "failed" ? "error" : run.status === "completed" ? "success" : "loading");
    setStatusLabel(run.status === "processing" ? "Thinking" : run.status);

    if (run.status === "completed" && !completedRuns.current.has(runId)) {
      completeAssistantAnswer(runId, run.answer ?? "The backend completed without an answer payload.");
      return true;
    }

    if (run.status === "failed" && !completedRuns.current.has(runId)) {
      completedRuns.current.add(runId);
      activeRunId.current = null;
      setChatMessages((current) => [
        ...current.filter((message) => message.id !== `pending-${runId}` && message.id !== `answer-${runId}`),
        {
          id: `error-${runId}`,
          role: "assistant",
          content: run.error ?? run.message ?? "Chat request failed.",
          error: true,
        },
      ]);
      return true;
    }

    return false;
  }

  function completeAssistantAnswer(runId: string, answer: string) {
    completedRuns.current.add(runId);
    activeRunId.current = null;
    const answerId = `answer-${runId}`;
    setChatMessages((current) => [
      ...current.filter((message) => message.id !== `pending-${runId}` && message.id !== answerId),
      { id: answerId, role: "assistant", content: answer, pending: false },
    ]);
    setStatus("success");
    setStatusLabel("Completed");
    listChatSessions().then(setSessions).catch(() => undefined);
  }

  function handleStreamEvent(runId: string, event: ChatStreamEvent) {
    const answerId = `answer-${runId}`;
    if (event.type === "start") {
      setStatus("loading");
      setStatusLabel("Thinking");
      setChatMessages((current) =>
        [...current.filter((message) => message.id !== `pending-${runId}` && message.id !== answerId), { id: answerId, role: "assistant", content: "", pending: true }],
      );
      return;
    }
    if (event.type === "token") {
      setStatusLabel("Streaming");
      setChatMessages((current) => current.map((message) => message.id === answerId ? { ...message, content: message.content + event.content, pending: true } : message));
      return;
    }
    if (event.type === "status") {
      setStatusLabel(event.status);
      return;
    }
    if (event.type === "done") {
      const streamed = chatMessages.find((message) => message.id === answerId)?.content;
      completeAssistantAnswer(runId, event.answer || streamed || "The backend completed without an answer payload.");
      chatStreamSocket.current = null;
      return;
    }
    if (event.type === "error") {
      completedRuns.current.add(runId);
      activeRunId.current = null;
      setStatus("error");
      setStatusLabel("Error");
      setChatMessages((current) => [
        ...current.filter((message) => message.id !== `pending-${runId}` && message.id !== answerId),
        { id: `error-${runId}`, role: "assistant", content: event.message, error: true },
      ]);
      chatStreamSocket.current = null;
    }
  }

  function startPollingFallback(runId: string) {
    if (chatPollTimer.current || completedRuns.current.has(runId)) return;
    const poll = () => {
      pollRun(runId)
        .then((isDone) => {
          if (isDone && chatPollTimer.current) {
            window.clearInterval(chatPollTimer.current);
            chatPollTimer.current = null;
          }
        })
        .catch((error: unknown) => {
          if (chatPollTimer.current) window.clearInterval(chatPollTimer.current);
          chatPollTimer.current = null;
          if (isAuthenticationExpiredError(error)) return;
          setStatus("error");
          setStatusLabel("Error");
        });
    };
    void poll();
    chatPollTimer.current = window.setInterval(poll, 1200);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || status === "loading") {
      return;
    }

    setDraft("");
    setStatus("loading");
    setStatusLabel("Waiting");
    setChatMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: message },
      { id: "pending-local", role: "assistant", content: "Starting agent workflow...", pending: true },
    ]);

    try {
      const run = await createChatRun(message, activeSessionId);
      activeRunId.current = run.run_id;
      stoppedRuns.current.delete(run.run_id);
      setActiveSessionId(run.chat_session_id);
      onEvents(run.events);
      setChatMessages((current) => [
        ...current.filter((item) => item.id !== "pending-local"),
        { id: `pending-${run.run_id}`, role: "assistant", content: run.message || "Agent is thinking...", pending: true },
      ]);

      chatStreamSocket.current = await connectChatRunStream(
        run.run_id,
        (streamEvent) => handleStreamEvent(run.run_id, streamEvent),
        () => {
          if (!stoppedRuns.current.has(run.run_id)) startPollingFallback(run.run_id);
        },
      );
    } catch (error) {
      if (isAuthenticationExpiredError(error)) return;
      setStatus("error");
      setStatusLabel("Error");
      setChatMessages((current) => [
        ...current.filter((item) => item.id !== "pending-local"),
        {
          id: `submit-error-${Date.now()}`,
          role: "assistant",
          content: error instanceof Error ? error.message : "Chat request failed.",
          error: true,
        },
      ]);
    }
  }

  function handleStop() {
    const runId = activeRunId.current;
    const hadActiveRun = Boolean(runId || chatStreamSocket.current || chatPollTimer.current);
    if (runId) stoppedRuns.current.add(runId);
    activeRunId.current = null;
    if (chatStreamSocket.current) {
      chatStreamSocket.current.close(1000, "Stopped locally");
      chatStreamSocket.current = null;
    }
    if (chatPollTimer.current) {
      window.clearInterval(chatPollTimer.current);
      chatPollTimer.current = null;
    }
    if (hadActiveRun) {
      setStatus("idle");
      setStatusLabel("Stopped");
      setChatMessages((current) =>
        current.map((message) =>
          message.pending ? { ...message, content: `${message.content}\nStopped locally.`, pending: false } : message,
        ),
      );
    } else {
      setStatusLabel("No active run");
    }
  }

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || uploading) return;

    const uploadMessageId = `upload-${Date.now()}`;
    setUploading(true);
    setStatus("loading");
    setStatusLabel("Uploading");
    setChatMessages((current) => [
      ...current,
      {
        id: uploadMessageId,
        role: "assistant",
        content: `Uploading ${file.name} and starting ingest...`,
        pending: true,
      },
    ]);
    onLocalEvent("upload queued", `Uploading ${file.name} and starting ingest...`, "loading");

    try {
      const accepted = await uploadDocument(file);
      onLocalEvent(accepted.phase ?? accepted.status, accepted.message, accepted.status === "failed" ? "error" : "loading");
      setChatMessages((current) =>
        current.map((message) =>
          message.id === uploadMessageId
            ? { ...message, content: `${accepted.phase ?? accepted.status}: ${accepted.message}`, pending: Boolean(accepted.job_id) }
            : message,
        ),
      );

      if (!accepted.job_id) {
        setStatus("success");
        setStatusLabel("Uploaded");
        return;
      }

      const timer = window.setInterval(() => {
        getUploadStatus(accepted.job_id as string)
          .then((job) => {
            onLocalEvent(job.phase ?? job.status, job.message, job.status === "failed" ? "error" : job.status === "completed" ? "success" : "loading");
            setChatMessages((current) =>
              current.map((message) =>
                message.id === uploadMessageId
                  ? {
                      ...message,
                      content: `${job.phase ?? job.status}: ${job.message}`,
                      pending: job.status !== "completed" && job.status !== "failed",
                      error: job.status === "failed",
                    }
                  : message,
              ),
            );

            if (job.status === "completed" || job.status === "failed") {
              window.clearInterval(timer);
              setUploading(false);
              setStatus(job.status === "completed" ? "success" : "error");
              setStatusLabel(job.status === "completed" ? "Indexed" : "Failed");
            }
          })
          .catch((error: unknown) => {
            window.clearInterval(timer);
            setUploading(false);
            if (isAuthenticationExpiredError(error)) return;
            setStatus("error");
            setStatusLabel("Upload error");
            setChatMessages((current) =>
              current.map((message) =>
                message.id === uploadMessageId
                  ? { ...message, content: error instanceof Error ? error.message : "Upload polling failed.", pending: false, error: true }
                  : message,
              ),
            );
          });
      }, 2000);
    } catch (error) {
      setUploading(false);
      if (isAuthenticationExpiredError(error)) return;
      setStatus("error");
      setStatusLabel("Upload error");
      setChatMessages((current) =>
        current.map((message) =>
          message.id === uploadMessageId
            ? {
                ...message,
                content: error instanceof Error ? error.message : "Upload failed.",
                pending: false,
                error: true,
              }
            : message,
        ),
      );
    } finally {
      event.target.value = "";
    }
  }

  return (
    <div className="grid h-full min-h-[calc(100vh-112px)] grid-rows-[minmax(0,1fr)_auto] gap-4">
      <Panel className="flex min-h-0 flex-col p-4 md:p-6">
        {sessions.length ? (
          <div className="mb-4 flex shrink-0 gap-2 overflow-x-auto border-b border-white/10 pb-4">
            <button
              aria-label="Start new conversation"
              className="focus-ring grid h-8 w-8 shrink-0 place-items-center rounded-rag bg-midnight-highest text-rag-muted hover:text-rag-text"
              title="Start new conversation"
              type="button"
              onClick={startNewSession}
            >
              <Plus className="h-4 w-4" />
            </button>
            {sessions.slice(0, 8).map((session) => (
              <button
                key={session.run_id}
                className={`max-w-52 shrink-0 truncate rounded-rag px-3 py-2 text-left text-xs hover:text-rag-text ${activeSessionId === session.run_id ? "bg-rag-primaryStrong/25 text-rag-primary" : "bg-midnight-highest text-rag-muted"}`}
                title={session.title}
                type="button"
                onClick={() => openSession(session)}
              >
                {session.title}
              </button>
            ))}
          </div>
        ) : null}
        <div className="min-h-0 flex-1 space-y-4 overflow-auto pr-1">
          {!chatMessages.length ? (
            <div className="grid h-full min-h-[240px] place-items-center rounded-rag-lg border border-dashed border-rag-outline/40 bg-midnight-lowest/35 p-6 text-center text-sm leading-6 text-rag-muted">
              Send a query to start a backend chat run. The full session transcript will stay here and scroll as it grows.
            </div>
          ) : null}
          {chatMessages.map((message) => (
            <article
              key={message.id}
              className={`max-w-3xl rounded-rag-lg p-4 text-sm leading-6 ${
                message.role === "user"
                  ? "ml-auto bg-rag-primaryStrong/20 text-rag-primary"
                  : message.error
                    ? "border border-rag-error/50 bg-rag-error/10 text-rag-error"
                    : "border border-rag-outline/40 bg-midnight-lowest/60 text-rag-text"
              }`}
            >
              <div className="mb-2 flex items-center gap-2">
                {message.role === "assistant" && <Bot className="h-4 w-4 text-rag-secondary" />}
                <span className="label-caps text-rag-muted">{message.role}</span>
                {message.pending ? <Loader2 className="h-3.5 w-3.5 animate-spin text-rag-secondary" /> : null}
              </div>
              <MarkdownContent content={message.content} />
              {message.citations?.length ? (
                <div className="mt-3 flex gap-2">
                  {message.citations.map((id) => (
                    <span key={id} className="rounded-full bg-rag-secondary/10 px-2 py-0.5 font-mono text-xs text-rag-secondary">
                      [{id}]
                    </span>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </Panel>

      <Panel className="p-3 md:p-4">
        <div className="flex items-center justify-between gap-3 pb-3">
          <StatusPill label={statusLabel} tone={status} />
          <span className="label-caps text-rag-muted">Context window: {contextWindow}</span>
        </div>
        <form className="flex items-end gap-2" onSubmit={handleSubmit}>
          <label
            aria-label="Upload and ingest document"
            className="focus-ring grid h-10 w-10 cursor-pointer place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
            title="Upload and ingest document"
          >
            <input
              className="sr-only"
              disabled={uploading}
              type="file"
              accept=".pdf,.docx,.md,.png,.jpg,.jpeg,.webp,.bmp,.gif"
              onChange={handleUpload}
            />
            <Paperclip className="h-4 w-4" />
          </label>
          <textarea
            className="min-h-[72px] flex-1 resize-none rounded-rag border border-rag-outline/40 bg-midnight-lowest px-3 py-2 text-sm text-rag-text outline-none placeholder:text-rag-muted focus:border-rag-secondary"
            placeholder="Ask the agent anything..."
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button
            aria-label="Stop generation"
            className="focus-ring grid h-10 w-10 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-error/15 hover:text-rag-error"
            type="button"
            onClick={handleStop}
          >
            <Square className="h-4 w-4" />
          </button>
          <button
            className="focus-ring grid h-10 w-10 place-items-center rounded-rag bg-rag-primaryStrong text-rag-primary transition hover:bg-[#6258ff] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={status === "loading"}
            type="submit"
          >
            {status === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </Panel>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ children, ...props }) => (
            <a className="text-rag-secondary underline underline-offset-2" target="_blank" rel="noreferrer" {...props}>
              {children}
            </a>
          ),
          code: ({ children, className, ...props }) => (
            <code className={`${className ?? ""} rounded bg-midnight-highest px-1 py-0.5 font-mono text-[0.9em] text-rag-secondary`} {...props}>
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-3 max-w-full overflow-auto rounded-rag border border-white/10 bg-midnight-lowest p-3 font-mono text-xs leading-5">
              {children}
            </pre>
          ),
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
          p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
          table: ({ children }) => (
            <div className="my-3 overflow-auto">
              <table className="min-w-full border-collapse border border-white/10 text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-white/10 bg-midnight-highest px-2 py-1 text-rag-primary">{children}</th>,
          td: ({ children }) => <td className="border border-white/10 px-2 py-1">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
