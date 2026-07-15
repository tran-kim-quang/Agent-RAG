"use client";

import { useEffect, useMemo, useState } from "react";
import { getHealth, logout, refreshSession, type AgentRunEvent, type User } from "@/lib/api/backend";
import type { AwaitedReturn } from "@/lib/utility-types";
import { getDashboardData } from "@/lib/api/dashboard";
import type { ReasoningStep, ViewId } from "@/lib/types";
import { AppShell } from "./app-shell";
import { ChatView } from "./chat-view";
import { Inspector } from "./inspector";
import { KnowledgeView } from "./knowledge-view";
import { StatusView } from "./status-view";
import { AdminView } from "./admin-view";
import { AuthView } from "./auth-view";

type DashboardData = AwaitedReturn<typeof getDashboardData>;

export function DashboardClient({ data }: { data: DashboardData }) {
  const [activeView, setActiveView] = useState<ViewId>("chat");
  const [statusLabel, setStatusLabel] = useState(data.commandCenter.activeStatus);
  const [liveEvents, setLiveEvents] = useState<ReasoningStep[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    refreshSession().then((auth) => setUser(auth.user)).catch(() => setUser(null)).finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    getHealth()
      .then((health) => {
        setStatusLabel(health.status === "ok" ? data.commandCenter.activeStatus : `Backend ${health.status}`);
      })
      .catch(() => {
        setStatusLabel("Backend Offline");
      });
  }, [data.commandCenter.activeStatus, user]);

  const navigation = useMemo(() => {
    if (!user) return [];
    const base = data.primaryNavigation.filter((item) => item.id !== "status" || user.role === "admin");
    return user.role === "admin" ? [...base, { id: "admin" as const, label: "Administration", icon: "shield" as const }] : base;
  }, [data.primaryNavigation, user]);

  const inspectorSteps = useMemo(() => {
    return liveEvents.length ? liveEvents : [];
  }, [liveEvents]);

  function handleBackendEvents(events: AgentRunEvent[]) {
    setLiveEvents(
      events.map((event, index) => ({
        id: `${event.timestamp}-${event.phase}-${index}`,
        label: event.phase.replaceAll("_", " "),
        duration: event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "",
        detail: event.message,
        tone: event.phase.includes("failed") ? "error" : "success",
        timestamp: event.timestamp,
      })),
    );
  }

  function appendLocalEvent(label: string, detail: string, tone: ReasoningStep["tone"] = "loading") {
    setLiveEvents((current) => [
      ...current,
      {
        id: `${Date.now()}-${label}`,
        label,
        duration: new Date().toLocaleTimeString(),
        detail,
        tone,
      },
    ]);
  }

  if (authLoading) return <div className="grid min-h-screen place-items-center bg-midnight-lowest text-sm text-rag-muted">Restoring session...</div>;
  if (!user) return <AuthView onAuthenticated={(auth) => setUser(auth.user)} />;

  return (
    <AppShell
      activeView={activeView}
      onViewChange={setActiveView}
      primaryNavigation={navigation}
      statusLabel={statusLabel}
      user={user}
      onLogout={() => { logout().finally(() => { setUser(null); setActiveView("chat"); }); }}
      inspector={
        <Inspector
          steps={inspectorSteps}
          citations={[]}
          entities={[]}
          logs={[]}
          resourceUtilization={data.commandCenter.resourceUtilization}
        />
      }
    >
      <div className={activeView === "chat" ? "block h-full" : "hidden h-full"}>
        <ChatView
          messages={[]}
          contextWindow={data.commandCenter.contextWindow}
          onEvents={handleBackendEvents}
          onLocalEvent={appendLocalEvent}
        />
      </div>
      <div className={activeView === "knowledge" ? "block" : "hidden"}>
        <KnowledgeView onLocalEvent={appendLocalEvent} />
      </div>
      <div className={activeView === "status" ? "block" : "hidden"}>
        {user.role === "admin" ? <StatusView activeStatus={statusLabel} /> : null}
      </div>
      <div className={activeView === "admin" ? "block" : "hidden"}>
        {user.role === "admin" ? <AdminView /> : null}
      </div>
    </AppShell>
  );
}
