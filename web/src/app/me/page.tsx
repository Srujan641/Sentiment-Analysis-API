"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Notice, formatDate } from "@/components/app/ui";
import { usePersonal } from "@/components/personal/PersonalShell";
import { api, ApiError, type PersonalUsage, type ResearchItem } from "@/lib/api";

const EXAMPLES = ["boAt Rockerz 450", "Noise ColorFit Pro 5", "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4"];

export default function ResearchHome() {
  const me = usePersonal();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [usage, setUsage] = useState<PersonalUsage | null>(null);
  const [history, setHistory] = useState<ResearchItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [u, h] = await Promise.all([api<PersonalUsage>("/v1/usage"), api<ResearchItem[]>("/v1/research")]);
    setUsage(u);
    setHistory(h);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    // "Research this instead" links arrive as /me?q=...
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) setQuery(q);
  }, [load]);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return setError("Paste a product link or type a product name.");
    setBusy(true);
    setError(null);
    try {
      const r = await api<ResearchItem>("/v1/research", { method: "POST", json: { query: query.trim() } });
      router.push(`/me/research/${r.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start the research.");
      setBusy(false);
    }
  }

  const t = usage?.research_today;
  const left = t && t.limit !== null ? Math.max(0, t.limit - t.used) : null;

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Hi {me.user.name.split(" ")[0]}, what are you thinking of buying?</h1>
      <p className="mt-1 text-sm text-muted">
        Paste a product link (Amazon, Flipkart, Google or any shop) or type its name. We read reviews from across the web and tell you
        what it&apos;s good at, what it&apos;s lacking, and what to compare it with.
      </p>

      <form onSubmit={start} className="card mt-6 p-5">
        <label htmlFor="q" className="label">
          Product link or name
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input id="q" className="input flex-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="https://www.amazon.in/… or “Sony WH-1000XM5”" maxLength={2000} />
          <button className="btn btn-primary" disabled={busy || left === 0}>
            {busy ? "Starting…" : "Research"}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Try:</span>
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="rounded-full border border-border px-2.5 py-1 hover:text-fg" onClick={() => setQuery(x)}>
              {x.length > 40 ? x.slice(0, 40) + "…" : x}
            </button>
          ))}
        </div>
        {t && (
          <p className="mt-4 text-sm text-muted">
            {t.used} of {t.limit ?? "unlimited"} researches used in the last 24 hours
            {left === 0 && t.next_free_at ? ` · next available at ${new Date(t.next_free_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}` : ""}.
          </p>
        )}
      </form>
      {error && (
        <div className="mt-4">
          <Notice tone="neg">{error}</Notice>
        </div>
      )}

      <h2 className="mb-3 mt-10 font-semibold">Your research</h2>
      {history && history.length === 0 && <p className="text-sm text-muted">Nothing yet. Your researches will appear here.</p>}
      <ul className="card divide-y divide-border">
        {history?.map((r) => (
          <li key={r.id}>
            <Link href={`/me/research/${r.id}`} className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-surface-2">
              <span className="min-w-0">
                <span className="block truncate font-medium">{r.product_name ?? r.query}</span>
                <span className="text-xs text-muted">{formatDate(r.created_at)}</span>
              </span>
              <span className={`shrink-0 text-xs ${r.status === "failed" ? "text-neg" : "text-muted"}`}>
                {r.status === "complete" ? "Ready" : r.status === "failed" ? "Failed" : "Researching…"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
