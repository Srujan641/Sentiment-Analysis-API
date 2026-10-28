"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Empty, Notice, formatDate } from "@/components/app/ui";
import { api, ApiError, type CollectionRun, type ConnectorInfo, type Source, type SourceCandidate } from "@/lib/api";

export function Sources({ productId, productName, onCollected }: { productId: string; productName: string; onCollected: () => void }) {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [sources, setSources] = useState<Source[] | null>(null);
  const [connector, setConnector] = useState("app_store");
  const [query, setQuery] = useState(productName);
  const [candidates, setCandidates] = useState<SourceCandidate[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [run, setRun] = useState<CollectionRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<(id: string) => void>(() => undefined);

  const loadSources = useCallback(async () => setSources(await api<Source[]>(`/v1/products/${productId}/sources`)), [productId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSources();
    api<ConnectorInfo[]>("/v1/connectors").then(setConnectors).catch(() => undefined);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loadSources]);

  const poll = useCallback(
    async (id: string) => {
      const r = await api<CollectionRun>(`/v1/collections/${id}`);
      setRun(r);
      if (r.status === "queued" || r.status === "running") {
        timer.current = setTimeout(() => pollRef.current(id), 2000);
      } else {
        await loadSources();
        onCollected();
      }
    },
    [loadSources, onCollected],
  );
  useEffect(() => {
    pollRef.current = (id: string) => void poll(id);
  }, [poll]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    setSearching(true);
    setError(null);
    setCandidates(null);
    try {
      setCandidates(
        await api<SourceCandidate[]>(`/v1/products/${productId}/sources/suggest?connector=${connector}&q=${encodeURIComponent(query)}`),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  async function add(c: SourceCandidate) {
    setError(null);
    try {
      await api(`/v1/products/${productId}/sources`, { method: "POST", json: { connector: c.connector, ref: c.ref, label: c.label, url: c.url } });
      await loadSources();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the source.");
    }
  }

  async function remove(s: Source) {
    await api(`/v1/products/${productId}/sources/${s.id}`, { method: "DELETE" });
    await loadSources();
  }

  async function collect() {
    setError(null);
    try {
      const r = await api<CollectionRun>(`/v1/products/${productId}/collect`, { method: "POST" });
      setRun(r);
      void poll(r.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start collecting.");
    }
  }

  const added = new Set((sources ?? []).map((s) => `${s.connector}|${s.ref}`));
  const busy = run?.status === "queued" || run?.status === "running";
  const labelOf = (name: string) => connectors.find((c) => c.name === name)?.label ?? name;
  const selected = connectors.find((c) => c.name === connector);

  return (
    <div className="space-y-5">
      <section className="card p-5">
        <div className="font-medium">Find sources</div>
        <p className="mt-0.5 text-sm text-muted">
          Search a source for this product, then add the right matches. Marketplaces whose terms forbid automated collection (Amazon,
          Flipkart and similar) are never collected; upload their exports instead.
        </p>
        <form onSubmit={search} className="mt-4 flex flex-wrap gap-2">
          <select className="input w-auto" value={connector} onChange={(e) => setConnector(e.target.value)} aria-label="Source type">
            {connectors.map((c) => (
              <option key={c.name} value={c.name} disabled={!c.available}>
                {c.label}
                {c.available ? "" : " (not set up)"}
              </option>
            ))}
          </select>
          <input className="input min-w-[200px] flex-1" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search text" />
          <button className="btn btn-primary" disabled={searching || !selected?.available}>
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
        {connectors.filter((c) => !c.available).map((c) => (
          <p key={c.name} className="mt-2 text-xs text-muted">
            {c.label}: {c.requires}
          </p>
        ))}

        {candidates && (
          <ul className="mt-4 divide-y divide-border rounded-lg border border-border">
            {candidates.length === 0 && <li className="px-4 py-3 text-sm text-muted">No matches. Try a different search.</li>}
            {candidates.map((c) => (
              <li key={c.ref} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{c.label}</div>
                  <div className="truncate text-xs text-muted">
                    {c.detail}
                    {c.url && (
                      <>
                        {" · "}
                        <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                          open
                        </a>
                      </>
                    )}
                  </div>
                  {!c.allowed && <div className="mt-1 text-xs text-warn">{c.reason}</div>}
                </div>
                {added.has(`${c.connector}|${c.ref}`) ? (
                  <span className="text-sm text-muted">Added</span>
                ) : (
                  <button className="btn btn-secondary btn-sm" disabled={!c.allowed} onClick={() => add(c)}>
                    Add
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {error && <Notice tone="neg">{error}</Notice>}

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Sources for this product</h2>
          <button className="btn btn-primary" onClick={collect} disabled={busy || !sources?.length}>
            {busy ? "Collecting…" : "Collect reviews now"}
          </button>
        </div>

        {busy && run && <Notice tone="info">{run.stage ?? "Queued…"}</Notice>}
        {run?.status === "complete" && run.results && (
          <Notice tone="pos">
            {run.results
              .map((r) =>
                r.error
                  ? `${r.label}: ${r.error}`
                  : `${r.label}: ${r.added ?? 0} new review${r.added === 1 ? "" : "s"}${r.duplicates ? ` (${r.duplicates} already had)` : ""}${
                      r.skipped_over_quota ? `, ${r.skipped_over_quota} skipped: monthly limit reached` : ""
                    }`,
              )
              .join(" · ")}
            . Run an analysis on the Insights tab to include them.
          </Notice>
        )}
        {run?.status === "failed" && <Notice tone="neg">Collection failed: {run.error}</Notice>}

        {sources && sources.length === 0 ? (
          <div className="mt-3">
            <Empty title="No sources yet" body="Search above and add the app, page or video where customers review this product." />
          </div>
        ) : (
          <ul className="card mt-3 divide-y divide-border">
            {sources?.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{s.label}</div>
                  <div className="text-xs text-muted">
                    {labelOf(s.connector)}
                    {s.last_collected_at
                      ? ` · collected ${formatDate(s.last_collected_at)}${s.last_added != null ? `, ${s.last_added} new` : ""}`
                      : " · not collected yet"}
                  </div>
                  {s.last_error && <div className="mt-1 text-xs text-neg">{s.last_error}</div>}
                </div>
                <button className="text-sm text-muted hover:text-neg" onClick={() => remove(s)} aria-label={`Remove ${s.label}`}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
