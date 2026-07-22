import { clsx } from "clsx";
import type { ComponentPropsWithoutRef } from "react";
import type { StatusTone } from "@/lib/types";

const statusToneClasses: Record<StatusTone, string> = {
  idle: "text-rag-muted",
  loading: "text-rag-secondary",
  success: "text-rag-success",
  warning: "text-rag-warning",
  error: "text-rag-error",
};

export function StatusPill({ label, tone = "idle" }: { label: string; tone?: StatusTone }) {
  return (
    <span className={clsx("label-caps inline-flex min-h-6 items-center rounded-rag bg-midnight-highest px-2 py-1", statusToneClasses[tone])}>
      {label}
    </span>
  );
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="label-caps text-rag-muted">{children}</p>;
}

export function Panel({
  children,
  className,
  ...props
}: ComponentPropsWithoutRef<"section">) {
  return (
    <section className={clsx("glass-panel min-w-0 overflow-hidden", className)} {...props}>
      {children}
    </section>
  );
}

export function IconButton({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <button
      aria-label={label}
      className="focus-ring grid h-7 w-7 place-items-center rounded-rag bg-midnight-highest/70 text-rag-muted transition hover:bg-rag-primaryStrong/20 hover:text-rag-text"
      type="button"
    >
      {children}
    </button>
  );
}
