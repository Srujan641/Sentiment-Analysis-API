"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "@/components/app/AppShell";
import { Empty, Notice, formatDate } from "@/components/app/ui";
import { api, ApiError, type AnalysisRun, type AspectStat, type FixResult, type Quote, type Report } from "@/lib/api";

// Sentence case: "price and value" -> "Price and value" (CSS capitalize would give "Price And Value").
const label = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const pct = (x: number | null | undefined, digits = 0) => (x == null ? "–" : `${(x * 100).toFixed(digits)}%`);

export function Insights({ productId, reviewCount }: { productId: string; reviewCount: number }) {
  const { me } = useSession();
  const paid = me.organization.plan !== "free";
  const [report, setReport] = useState<Report | null>(null);
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<(id: string) => void>(() => undefined);

  const loadLatest = useCallback(async () => {
    const [runs, latest] = await Promise.all([
      api<AnalysisRun[]>(`/v1/products/${productId}/analyses`),
      api<Report>(`/v1/products/${productId}/insights`).catch((e) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }),
    ]);
    setReport(latest);
    const active = runs.find((r) => r.status === "queued" || r.status === "running") ?? null;
    setRun(active ?? runs[0] ?? null);
    setLoaded(true);
    return active;
  }, [productId]);

  const poll = useCallback(
    async (id: string) => {
      const r = await api<AnalysisRun>(`/v1/analyses/${id}`);
      setRun(r);
      if (r.status === "queued" || r.status === "running") {
        timer.current = setTimeout(() => pollRef.current(id), 2000);
      } else if (r.status === "complete") {
        setReport(await api<Report>(r.report_url));
      } else {
        setError(r.error ?? "The analysis failed.");
      }
    },
    [],
  );

  useEffect(() => {
    pollRef.current = (id: string) => void poll(id);
  }, [poll]);

  useEffect(() => {
    // Initial load; state updates happen after the awaits, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadLatest()
      .then((active) => active && poll(active.id))
      .catch((e: Error) => setError(e.message));
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loadLatest, poll]);

  async function start(kind: "quick" | "full") {
    setError(null);
    try {
      const r = await api<AnalysisRun>(`/v1/products/${productId}/analyses`, { method: "POST", json: { kind } });
      setRun(r);
      void poll(r.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the analysis.");
    }
  }

  const busy = run?.status === "queued" || run?.status === "running";

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <div className="font-medium">{report ? "Latest analysis" : "Analyse this product"}</div>
          <p className="mt-0.5 text-sm text-muted">
            {report
              ? `${report.kind === "full" ? "Full" : "Quick"} report on ${report.review_count.toLocaleString()} reviews · ${formatDate(report.generated_at)}`
              : `Find what customers complain about in ${reviewCount.toLocaleString()} reviews.`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary" disabled={busy || reviewCount === 0} onClick={() => start("quick")}>
            Run quick analysis
          </button>
          <button
            className="btn btn-primary"
            disabled={busy || reviewCount === 0 || !paid}
            onClick={() => start("full")}
            title={paid ? undefined : "Full reports need a paid plan"}
          >
            Run full analysis
          </button>
        </div>
        {!paid && (
          <p className="w-full text-xs text-muted">
            Full reports add weekly trends, fix verification and early warnings. They need a paid plan.
          </p>
        )}
      </div>

      {busy && run && (
        <Notice tone="info">
          <span className="inline-flex items-center gap-2">
            <span className="size-3 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />
            {run.status === "queued" ? "Queued…" : `Analysing: ${run.stage ?? "starting"}…`}
          </span>
        </Notice>
      )}
      {error && <Notice tone="neg">{error}</Notice>}

      {loaded && !report && !busy && (
        <Empty
          title="No analysis yet"
          body={reviewCount ? "Run a quick analysis to see what customers complain about most." : "Upload reviews first, then run an analysis."}
        />
      )}

      {report && <ReportView report={report} />}
    </div>
  );
}

/* ================================================================== report */
function ReportView({ report }: { report: Report }) {
  const o = report.overall;
  const trendFor = (aspect: string | null) => report.trends?.find((t) => t.aspect === aspect);
  return (
    <>
      <section className="card p-5">
        <h2 className="font-semibold">Summary</h2>
        <ul className="mt-2 space-y-1.5 text-fg-2">
          {report.summary.map((s) => (
            <li key={s} className="flex gap-2.5">
              <span className="mt-2.5 size-1 shrink-0 rounded-full bg-muted" aria-hidden="true" />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </section>

      {o && (
        <div className="grid gap-4 sm:grid-cols-4">
          <Kpi label="Sentiment score" value={`${o.sentiment_score > 0 ? "+" : ""}${o.sentiment_score}`} sub="−100 to +100" />
          <Kpi label="Positive reviews" value={pct(o.positive_share)} sub={`${report.review_count.toLocaleString()} analysed`} />
          <Kpi label="Average rating" value={o.average_rating != null ? `${o.average_rating.toFixed(2)}★` : "–"} sub={`${o.rated_reviews.toLocaleString()} rated`} />
          <Kpi
            label="Period"
            value={report.period?.to ? formatDate(report.period.to) : "–"}
            sub={report.period?.from ? `since ${formatDate(report.period.from)}` : "no dates"}
          />
        </div>
      )}

      {report.alerts && report.alerts.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-semibold">Early warnings</h2>
          {report.alerts.map((a) => (
            <div key={a.aspect} className="rounded-xl border border-warn-border bg-warn-bg p-5 text-warn">
              <div className="font-semibold">{label(a.aspect)}</div>
              <p className="mt-1 text-sm">
                Complaints rose to {pct(a.current_rate)} of recent reviews ({a.complaints} of {a.reviews}), up from a baseline of{" "}
                {pct(a.baseline_rate)}, since {formatDate(a.first_seen)}. p = {a.p_value.toFixed(4)}.
              </p>
              <Quotes quotes={a.quotes} tone="warn" />
            </div>
          ))}
        </section>
      )}

      <section>
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="font-semibold">What to fix first</h2>
          <span className="text-xs text-muted">Ranked by estimated star-rating impact</span>
        </div>
        {report.lacking.length === 0 ? (
          <div className="card p-5 text-sm text-muted">No recurring complaints found.</div>
        ) : (
          <IssueList items={report.lacking} />
        )}
      </section>

      {report.fix_verification && report.fix_verification.length > 0 && (
        <section>
          <h2 className="mb-3 font-semibold">Did your fixes work?</h2>
          <div className="space-y-4">
            {report.fix_verification.map((fv) => (
              <div key={fv.change_id} className="card p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium">{fv.description}</span>
                  <span className="text-sm text-muted">Shipped {formatDate(fv.changed_on)}</span>
                </div>
                <div className="mt-4 space-y-5">
                  {fv.results.map((r) => (
                    <FixCard key={r.requested} result={r} changedOn={fv.changed_on} trend={trendFor(r.aspect)} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {report.kind === "full" && (!report.fix_verification || report.fix_verification.length === 0) && (
        <Notice tone="info">Log a product change on the “Product changes” tab to verify whether it reduced complaints.</Notice>
      )}

      {report.strengths.length > 0 && (
        <section>
          <h2 className="mb-3 font-semibold">What customers love</h2>
          <ul className="card divide-y divide-border">
            {report.strengths.map((s) => (
              <li key={s.aspect} className="px-5 py-3.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{label(s.aspect)}</span>
                  <span className="text-sm tabular-nums text-pos">{s.positive.toLocaleString()} positive mentions</span>
                </div>
                {s.quotes[0] && <p className="mt-1 text-sm text-fg-2">“{s.quotes[0].text}”</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.methodology && (
        <details className="text-sm text-muted">
          <summary className="cursor-pointer select-none font-medium">How this was calculated</summary>
          <dl className="mt-3 space-y-2">
            {Object.entries(report.methodology).map(([k, v]) => (
              <div key={k} className="grid gap-1 sm:grid-cols-[180px_1fr]">
                <dt className="capitalize">{k.replaceAll("_", " ")}</dt>
                <dd className="text-fg-2">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs font-medium uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="text-xs text-muted">{sub}</div>
    </div>
  );
}

const SHOWN = 8;

function IssueList({ items }: { items: AspectStat[] }) {
  const [all, setAll] = useState(false);
  const visible = all ? items : items.slice(0, SHOWN);
  return (
    <>
      <ol className="card divide-y divide-border">
        {visible.map((s, i) => (
          <IssueRow key={s.aspect} rank={i + 1} stat={s} max={items[0].negative_share} />
        ))}
      </ol>
      {items.length > SHOWN && (
        <button className="mt-2 text-sm text-muted hover:text-fg" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show ${items.length - SHOWN} smaller issues`}
        </button>
      )}
    </>
  );
}

function IssueRow({ rank, stat, max }: { rank: number; stat: AspectStat; max: number }) {
  const [open, setOpen] = useState(rank === 1);
  return (
    <li>
      <button className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-surface-2" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="w-5 shrink-0 text-sm tabular-nums text-muted">{rank}</span>
        <span className="min-w-0 flex-1">
          <span className="font-medium">{label(stat.aspect)}</span>
          {stat.discovered && (
            <span className="ml-2 rounded border border-border px-1.5 py-0.5 text-[11px] text-muted">found in reviews</span>
          )}
          <span className="mt-1.5 block h-1.5 max-w-sm overflow-hidden rounded-full bg-border">
            <span className="block h-full rounded-full bg-neg" style={{ width: `${(stat.negative_share / (max || 1)) * 100}%` }} />
          </span>
        </span>
        <span className="hidden w-32 shrink-0 text-right text-sm sm:block">
          <span className="tabular-nums">{pct(stat.negative_share, 1)}</span>
          <span className="block text-xs text-muted">of reviews complain</span>
        </span>
        <span className="w-28 shrink-0 text-right text-sm">
          <span className="tabular-nums">{stat.rating_impact != null ? `−${stat.rating_impact.toFixed(2)}★` : "–"}</span>
          <span className="block text-xs text-muted">est. rating cost</span>
        </span>
      </button>
      {open && (
        <div className="space-y-3 px-5 pb-5 pl-14">
          <p className="text-sm text-muted">
            {stat.negative.toLocaleString()} complaints in {stat.mentions.toLocaleString()} reviews that mention it ({pct(stat.negative_rate)} negative).
          </p>
          {stat.specific_issues && stat.specific_issues.length > 0 && (
            <div>
              <div className="text-xs font-medium uppercase tracking-wider text-muted">Specifically</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {stat.specific_issues.map((s) => (
                  <span key={s.name} className="rounded-md border border-neg-border bg-neg-bg px-2 py-0.5 text-xs text-neg">
                    {s.name} · {s.mentions}
                  </span>
                ))}
              </div>
            </div>
          )}
          <Quotes quotes={stat.quotes} />
        </div>
      )}
    </li>
  );
}

function Quotes({ quotes, tone }: { quotes: Quote[]; tone?: "warn" }) {
  if (!quotes.length) return null;
  return (
    <ul className="space-y-2">
      {quotes.map((q) => (
        <li key={q.review_id + q.text} className={`border-l-2 pl-3 text-sm ${tone === "warn" ? "border-warn-border" : "border-border-strong text-fg-2"}`}>
          “{q.text}”
          <span className={`mt-0.5 block text-xs ${tone === "warn" ? "" : "text-muted"}`}>
            {[q.rating != null ? `${q.rating}★` : null, q.date ? formatDate(q.date) : null, q.source].filter(Boolean).join(" · ")}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ================================================================== fix verification */
const VERDICT: Record<FixResult["verdict"], { label: string; cls: string }> = {
  improved: { label: "Improved", cls: "border-pos-border bg-pos-bg text-pos" },
  worse: { label: "Got worse", cls: "border-neg-border bg-neg-bg text-neg" },
  no_significant_change: { label: "No significant change", cls: "border-border bg-surface-2 text-fg-2" },
  inconclusive: { label: "Inconclusive", cls: "border-warn-border bg-warn-bg text-warn" },
  not_enough_data: { label: "Not enough data yet", cls: "border-border bg-surface-2 text-muted" },
  unknown_aspect: { label: "Aspect not found", cls: "border-border bg-surface-2 text-muted" },
};

function FixCard({
  result,
  changedOn,
  trend,
}: {
  result: FixResult;
  changedOn: string;
  trend?: { weeks: { week: string; reviews: number; negative: number }[] };
}) {
  const v = VERDICT[result.verdict];
  return (
    <div className="grid gap-4 md:grid-cols-[1fr_320px]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{label(result.aspect ?? result.requested)}</span>
          <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${v.cls}`}>{v.label}</span>
        </div>
        {result.before_rate != null && result.after_rate != null && (
          <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
            <Stat label="Before" value={pct(result.before_rate, 1)} sub={`${result.reviews_before?.toLocaleString()} reviews`} />
            <Stat label="After" value={pct(result.after_rate, 1)} sub={`${result.reviews_after?.toLocaleString()} reviews`} />
            <Stat
              label="Effect"
              value={result.relative_change != null ? `${result.relative_change > 0 ? "+" : ""}${(result.relative_change * 100).toFixed(0)}%` : "–"}
              sub={
                result.ci_low != null && result.ci_high != null
                  ? `95% CI ${(result.ci_low * 100).toFixed(0)}% to ${(result.ci_high * 100).toFixed(0)}%`
                  : result.p_value != null
                    ? `p = ${result.p_value.toFixed(3)}`
                    : ""
              }
            />
          </div>
        )}
        <p className="mt-3 text-sm text-muted">
          {result.note}
          {result.p_value != null && result.verdict !== "not_enough_data" ? ` p = ${result.p_value.toFixed(3)}.` : ""}
          {result.method ? ` Method: ${result.method}.` : ""}
        </p>
      </div>
      {trend && <TrendChart weeks={trend.weeks} markDate={changedOn} />}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{sub}</div>
    </div>
  );
}

function TrendChart({ weeks, markDate }: { weeks: { week: string; reviews: number; negative: number }[]; markDate: string }) {
  // 4-week rolling complaint rate; weeks without reviews are skipped.
  const pts: { t: number; rate: number; n: number }[] = [];
  for (let i = 0; i < weeks.length; i++) {
    const win = weeks.slice(Math.max(0, i - 3), i + 1);
    const n = win.reduce((s, w) => s + w.reviews, 0);
    if (n >= 3) pts.push({ t: new Date(weeks[i].week).getTime(), rate: win.reduce((s, w) => s + w.negative, 0) / n, n });
  }
  if (pts.length < 3) return <div className="text-xs text-muted">Not enough dated reviews for a chart.</div>;
  const W = 320;
  const H = 120;
  const t0 = pts[0].t;
  const t1 = pts[pts.length - 1].t;
  const maxR = Math.max(0.05, ...pts.map((p) => p.rate)) * 1.15;
  const x = (t: number) => 8 + ((t - t0) / (t1 - t0 || 1)) * (W - 16);
  const y = (r: number) => H - 18 - (r / maxR) * (H - 30);
  const mark = new Date(markDate).getTime();
  const showMark = mark >= t0 && mark <= t1;
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Weekly complaint rate (4-week rolling) with the change date marked">
        <line x1="8" x2={W - 8} y1={y(0)} y2={y(0)} className="stroke-border" />
        {showMark && (
          <>
            <line x1={x(mark)} x2={x(mark)} y1="6" y2={H - 18} className="stroke-muted" strokeDasharray="3 4" />
            <text
              x={x(mark) > W - 60 ? x(mark) - 4 : x(mark) + 4}
              y="26"
              textAnchor={x(mark) > W - 60 ? "end" : "start"}
              className="fill-muted text-[10px]"
            >
              change
            </text>
          </>
        )}
        <polyline
          points={pts.map((p) => `${x(p.t)},${y(p.rate)}`).join(" ")}
          fill="none"
          className="stroke-fg"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <text x="8" y={H - 4} className="fill-muted text-[10px]">
          {new Date(t0).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })}
        </text>
        <text x={W - 8} y={H - 4} textAnchor="end" className="fill-muted text-[10px]">
          {new Date(t1).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })}
        </text>
        <text x="8" y="14" className="fill-muted text-[10px]">
          peak {((maxR / 1.15) * 100).toFixed(0)}%
        </text>
      </svg>
      <figcaption className="text-xs text-muted">Share of reviews complaining, 4-week rolling</figcaption>
    </figure>
  );
}
