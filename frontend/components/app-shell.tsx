"use client";

import { clsx } from "clsx";
import { useState } from "react";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import type { User } from "@/lib/api/backend";
import { iconMap } from "@/lib/icons";
import type { NavItem, ViewId } from "@/lib/types";
import { SectionLabel, StatusPill } from "./ui";

export function AppShell({
  activeView,
  onViewChange,
  primaryNavigation,
  children,
  inspector,
  statusLabel,
  user,
  onLogout,
}: {
  activeView: ViewId;
  onViewChange: (view: ViewId) => void;
  primaryNavigation: NavItem[];
  children: React.ReactNode;
  inspector: React.ReactNode;
  statusLabel: string;
  user: User;
  onLogout: () => void;
}) {
  const activeLabel = primaryNavigation.find((item) => item.id === activeView)?.label ?? "Dashboard";
  const [notice, setNotice] = useState("");
  const statusTone = statusLabel.toLowerCase().includes("offline") ? "error" : "success";

  function showNotice(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2400);
  }

  return (
    <div className="grid h-screen min-h-0 grid-cols-1 overflow-hidden bg-midnight-lowest lg:grid-cols-[280px_minmax(0,1fr)_360px] lg:grid-rows-[64px_minmax(0,1fr)]">
      <aside className="glass-subtle z-20 min-h-0 overflow-auto border-b border-white/10 lg:col-start-1 lg:row-span-2 lg:border-b-0 lg:border-r">
        <header className="flex min-h-[101px] items-center gap-2 border-b border-white/10 px-6 py-5">
          <div className="grid h-8 w-8 place-items-center rounded-rag bg-rag-primaryStrong text-sm text-rag-primary">▣</div>
          <div>
            <h1 className="text-2xl font-semibold leading-none text-rag-primary">Agent-RAG</h1>
            <p className="label-caps mt-1 text-rag-muted">AI Command Center</p>
          </div>
        </header>

        <nav className="flex gap-1 overflow-x-auto p-2 lg:grid lg:gap-1 lg:p-2 lg:pt-4" aria-label="Primary">
          {primaryNavigation.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              active={item.id === activeView}
              onClick={() => onViewChange(item.id as ViewId)}
            />
          ))}
        </nav>
        <div className="border-t border-white/10 p-4">
          <p className="truncate text-sm text-rag-text">{user.email}</p>
          <div className="mt-1 flex items-center justify-between gap-2">
            <span className="label-caps text-rag-muted">{user.role}</span>
            <button aria-label="Sign out" className="focus-ring grid h-8 w-8 place-items-center rounded-rag bg-midnight-highest text-rag-muted hover:text-rag-error" onClick={onLogout} type="button" title="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <header className="glass-subtle sticky top-0 z-10 flex min-h-16 items-center justify-between gap-4 border-b border-white/10 px-4 lg:col-span-2 lg:col-start-2 lg:row-start-1">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <div className="flex min-w-0 items-center gap-2">
            <Menu className="h-5 w-5 text-rag-secondary lg:hidden" />
            <strong className="truncate text-lg font-semibold text-rag-primary">{activeLabel}</strong>
            <span className="label-caps hidden text-rag-muted sm:inline">/ Synthetic Workspace</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {notice ? <span className="label-caps hidden text-rag-secondary xl:inline">{notice}</span> : null}
          <StatusPill label={statusLabel} tone={statusTone} />
          <button
            aria-label="Search"
            className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
            type="button"
            onClick={() => showNotice("Search command ready")}
          >
            <Search className="h-4 w-4" />
          </button>
          <button
            aria-label="Notifications"
            className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
            type="button"
            onClick={() => showNotice("No new notifications")}
          >
            <Bell className="h-4 w-4" />
          </button>
        </div>
      </header>

      <main className="min-h-0 min-w-0 overflow-auto p-4 md:p-6 lg:col-start-2 lg:row-start-2">{children}</main>

      <aside className="min-h-0 overflow-auto border-l border-white/10 bg-midnight-base/80 backdrop-blur-md lg:col-start-3 lg:row-start-2 lg:block">
        <div className="border-b border-white/10 p-4">
          <SectionLabel>Context Inspector</SectionLabel>
          <h2 className="mt-1 text-sm font-semibold text-rag-muted">AI Reasoning Engine</h2>
        </div>
        {inspector}
      </aside>
    </div>
  );
}

function NavButton({
  item,
  active,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = iconMap[item.icon];
  return (
    <button
      className={clsx(
        "focus-ring flex min-h-9 shrink-0 items-center gap-4 rounded-rag px-4 py-2 text-left text-sm transition",
        active
          ? "border-l-4 border-rag-primary bg-rag-primaryStrong/20 pl-5 text-rag-primary"
          : "text-rag-muted hover:bg-rag-primaryStrong/10 hover:text-rag-text",
      )}
      type="button"
      onClick={onClick}
    >
      <Icon className="h-5 w-5 shrink-0" />
      <span className="whitespace-nowrap">{item.label}</span>
    </button>
  );
}
