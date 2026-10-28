"use client";

import { useEffect, useRef } from "react";

export function Meter({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  // Red is reserved for negative sentiment; nearing a plan limit is a caution, not an error.
  const tone = pct >= 80 ? "bg-warn" : "bg-fg";
  return (
    <div className="card p-5">
      <div className="text-xs font-medium uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tabular-nums">{used.toLocaleString()}</span>
        <span className="text-sm text-muted">/ {limit === null ? "unlimited" : limit.toLocaleString()}</span>
      </div>
      {limit !== null && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
          <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

export function Empty({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="font-medium">{title}</div>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Notice({ tone, children }: { tone: "pos" | "neg" | "warn" | "info"; children: React.ReactNode }) {
  const cls = {
    pos: "border-pos-border bg-pos-bg text-pos",
    neg: "border-neg-border bg-neg-bg text-neg",
    warn: "border-warn-border bg-warn-bg text-warn",
    info: "border-border bg-surface-2 text-fg-2",
  }[tone];
  return (
    <div role={tone === "neg" ? "alert" : "status"} className={`rounded-lg border px-3.5 py-2.5 text-sm ${cls}`}>
      {children}
    </div>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-[min(520px,calc(100vw-32px))] rounded-xl border border-border bg-surface p-0 text-fg backdrop:bg-black/40"
    >
      <div className="p-6">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="mt-4">{children}</div>
      </div>
    </dialog>
  );
}

export function formatDate(iso: string | null) {
  if (!iso) return "–";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
