"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Notice, formatDate } from "@/components/app/ui";
import { api, type ResearchItem, type ResearchQuote } from "@/lib/api";

const label = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x * 100)}%`);

const CONFIDENCE: Record<string, { text: string; cls: string }> = {
  high: { text: "High confidence", cls: "border-pos-border bg-pos-bg text-pos" },
  medium: { text: "Medium confidence", cls: "border-border bg-surface-2 text-fg-2" },
  low: { text: "Low confidence: few reviews", cls: "border-warn-border bg-warn-bg text-warn" },
  insufficient: { text: "Not enough reviews", cls: "border-warn-border bg-warn-bg text-warn" },
};

const SOURCE_LABEL: Record<string, string> = {
  amazon_link: "Identified from your Amazon link",
  flipkart_link: "Identified from your Flipkart link",
  google_link: "Identified from your Google search",
  web_page: "Identified from the page you linked",
  url_path: "Identified from your link",
  name: "Searched by name",
};

export default function ResearchPage() {
  const { id } = useParams<{ id: string }>();
  const [item, setItem] = useState<ResearchItem | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<() => void>(() => undefined);

  const poll = useCallback(async () => {
    const r = await api<ResearchItem>(`/v1/research/${id}`);
    setItem(r);
    if (r.status === "queued" || r.status === "running") timer.current = setTimeout(() => pollRef.current(), 2000);
  }, [id]);

  useEffect(() => {
    pollRef.current = () => void poll();
  }, [poll]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void poll();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [poll]);

  if (!item) return <p className="text-sm text-muted">Loading…</p>;
  const r = item.result;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link href="/me" className="text-sm text-muted hover:text-fg">
        ← New research
      </Link>

      {(item.status === "queued" || item.status === "running") && (
        <div className="card p-6">
          <div className="font-medium">Researching {item.product_name ?? item.query}</div>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted">
            <span className="size-3 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />
            {item.stage ? label(item.stage) : "Starting"}…
          </p>
          <p className="mt-3 text-xs text-muted">This usually takes under a minute. You can leave this page; it&apos;ll be in your history.</p>
        </div>
      )}

      {item.status === "failed" && <Notice tone="neg">{item.error ?? "The research failed."}</Notice>}

      {r && (
        <>
          <div>
            <p className="text-xs text-muted">{SOURCE_LABEL[r.product.identified_from] ?? ""}</p>
            <h1 className="mt-1 text-[28px] font-semibold leading-tight tracking-tight">{r.product.name}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${CONFIDENCE[r.verdict.confidence].cls}`}>
                {CONFIDENCE[r.verdict.confidence].text}
              </span>
              <span className="text-muted">
                {r.verdict.review_count.toLocaleString()} reviews from {r.sources.length} source{r.sources.length === 1 ? "" : "s"} ·{" "}
                {formatDate(r.generated_at)}
              </span>
            </div>
          </div>

          {r.notes.map((n) => (
            <Notice key={n} tone="warn">
              {n}
            </Notice>
          ))}

          <section className="card p-5">
            <h2 className="font-semibold">Summary</h2>
            <ul className="mt-2 space-y-1.5 text-fg-2">
              {r.summary.map((s) => (
                <li key={s}>• {s}</li>
              ))}
            </ul>
            {r.verdict.positive_share != null && (
              <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4 text-center">
                <Stat label="Positive" value={pct(r.verdict.positive_share)} />
                <Stat label="Avg rating" value={r.verdict.average_rating ? `${r.verdict.average_rating.toFixed(1)}★` : "–"} />
                <Stat label="Reviews" value={r.verdict.review_count.toLocaleString()} />
              </div>
            )}
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <section className="card p-5">
              <h2 className="font-semibold text-pos">What people like</h2>
              {r.strengths.length === 0 && <p className="mt-2 text-sm text-muted">No clear strengths found.</p>}
              <ul className="mt-3 space-y-4">
                {r.strengths.map((s) => (
                  <li key={s.aspect}>
                    <div className="font-medium">{label(s.aspect)}</div>
                    <Quote q={s.quotes[0]} />
                  </li>
                ))}
              </ul>
            </section>
            <section className="card p-5">
              <h2 className="font-semibold text-neg">What it&apos;s lacking</h2>
              {r.lacking.length === 0 && <p className="mt-2 text-sm text-muted">No recurring complaints found.</p>}
              <ul className="mt-3 space-y-4">
                {r.lacking.map((s) => (
                  <li key={s.aspect}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-medium">{label(s.aspect)}</span>
                      <span className="text-xs text-muted">{pct(s.negative_share)} of reviews</span>
                    </div>
                    {s.specific_issues && s.specific_issues.length > 0 && (
                      <div className="mt-1 text-xs text-muted">Specifically: {s.specific_issues.map((x) => x.name).join(", ")}</div>
                    )}
                    <Quote q={s.quotes[0]} />
                  </li>
                ))}
              </ul>
            </section>
          </div>

          {r.competitors.length > 0 && (
            <section>
              <h2 className="mb-3 font-semibold">Alternatives to compare</h2>
              <div className="grid gap-4 md:grid-cols-3">
                {r.competitors.map((c) => (
                  <div key={c.name} className="card flex flex-col p-5">
                    <div className="font-medium">{c.name}</div>
                    {c.price && <div className="text-sm text-muted">{c.price}</div>}
                    {c.why && <p className="mt-2 text-sm text-fg-2">{c.why}</p>}
                    {c.pros.length > 0 && <p className="mt-2 text-sm"><span className="text-pos">+</span> {c.pros.join(" · ")}</p>}
                    {c.cons.length > 0 && <p className="mt-1 text-sm"><span className="text-neg">−</span> {c.cons.join(" · ")}</p>}
                    <Link href={`/me?q=${encodeURIComponent(c.name)}`} className="mt-auto pt-4 text-sm text-link underline-offset-4 hover:underline">
                      Research this instead
                    </Link>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">Alternatives and their pros and cons come from comparison articles; see sources below.</p>
            </section>
          )}

          <section>
            <h2 className="mb-2 font-semibold">Sources</h2>
            {r.sources.length === 0 ? (
              <p className="text-sm text-muted">No sources with reviews of this product were found.</p>
            ) : (
              <ul className="card divide-y divide-border text-sm">
                {r.sources.map((s) => (
                  <li key={(s.url ?? "") + s.label} className="flex items-center justify-between gap-3 px-5 py-3">
                    <span className="min-w-0 truncate">
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline-offset-4 hover:underline">
                          {s.label}
                        </a>
                      ) : (
                        s.label
                      )}
                      <span className="text-muted"> · {s.kind}</span>
                    </span>
                    <span className="shrink-0 text-muted">{s.reviews} reviews</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted">We never collect from marketplaces whose terms forbid it (such as Amazon and Flipkart pages).</p>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

function Quote({ q }: { q?: ResearchQuote }) {
  if (!q) return null;
  return (
    <p className="mt-1 border-l-2 border-border-strong pl-3 text-sm text-fg-2">
      “{q.text}”{q.rating != null && <span className="text-xs text-muted"> · {q.rating}★</span>}
    </p>
  );
}
