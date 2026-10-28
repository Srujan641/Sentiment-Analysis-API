"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/app/AppShell";
import { Empty, Notice, formatDate } from "@/components/app/ui";
import { FormError } from "@/components/forms/Field";
import { api, ApiError, type Change, type IngestResult, type Product, type Review } from "@/lib/api";

type Tab = "reviews" | "changes" | "insights";

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("reviews");

  const load = useCallback(async () => {
    try {
      setProduct(await api<Product>(`/v1/products/${id}`));
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "This product doesn't exist or isn't yours." : (e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function archive() {
    if (!product || !confirm(`Archive “${product.name}”? Its reviews are kept and the plan slot is freed.`)) return;
    await api(`/v1/products/${id}`, { method: "DELETE" });
    router.push("/app/products");
  }

  if (error) return <Notice tone="neg">{error}</Notice>;
  if (!product) return <div className="text-sm text-muted">Loading…</div>;

  return (
    <>
      <Link href="/app/products" className="text-sm text-muted hover:text-fg">
        ← Products
      </Link>
      <div className="mt-2">
        <PageHeader
          title={product.name}
          description={[product.brand, product.category, `${product.review_count.toLocaleString()} reviews`].filter(Boolean).join(" · ")}
          actions={
            !product.archived && (
              <button className="btn btn-secondary btn-sm" onClick={archive}>
                Archive
              </button>
            )
          }
        />
      </div>

      <div className="mb-5 flex gap-1 border-b border-border" role="tablist">
        {(
          [
            ["reviews", "Reviews"],
            ["changes", "Product changes"],
            ["insights", "Insights"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === key ? "border-fg text-fg" : "border-transparent text-muted hover:text-fg"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "reviews" && <ReviewsTab productId={id} onChanged={load} />}
      {tab === "changes" && <ChangesTab productId={id} />}
      {tab === "insights" && <InsightsTab count={product.review_count} />}
    </>
  );
}

/* ------------------------------------------------------------------ reviews */
function ReviewsTab({ productId, onChanged }: { productId: string; onChanged: () => void }) {
  const [page, setPage] = useState<{ items: Review[]; total: number } | null>(null);
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const LIMIT = 25;

  const load = useCallback(async () => {
    setPage(await api(`/v1/products/${productId}/reviews?limit=${LIMIT}&offset=${offset}`));
  }, [productId, offset]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    const body = new FormData();
    body.append("file", file);
    try {
      setResult(await api<IngestResult>(`/v1/products/${productId}/reviews/upload`, { method: "POST", body }));
      setOffset(0);
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <div className="font-medium">Upload a review export</div>
          <p className="mt-0.5 text-sm text-muted">
            CSV, JSON or JSONL up to 10 MB, with a text/review column and optional rating and date.{" "}
            <Link href="/docs#reviews" className="underline underline-offset-4">
              Format details
            </Link>
          </p>
        </div>
        <label className={`btn btn-primary cursor-pointer ${busy ? "pointer-events-none opacity-60" : ""}`}>
          {busy ? "Uploading…" : "Choose file"}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.json,.jsonl,text/csv,application/json"
            className="sr-only"
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
        </label>
      </div>

      {result && (
        <Notice tone="pos">
          Added {plural(result.added, "review")}. Skipped {plural(result.duplicates, "duplicate")} and{" "}
          {plural(result.rejected, "empty row")}.
          {result.remaining_this_month !== null && ` ${result.remaining_this_month.toLocaleString()} left this month.`}
        </Notice>
      )}
      <FormError message={error} />

      {page && page.total === 0 ? (
        <Empty title="No reviews yet" body="Upload an export above, or push reviews with the API." />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-medium">Review</th>
                <th className="px-5 py-3 font-medium">Rating</th>
                <th className="px-5 py-3 font-medium">Date</th>
                <th className="px-5 py-3 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {page?.items.map((r) => (
                <tr key={r.id}>
                  <td className="max-w-[520px] px-5 py-3 text-fg-2">{r.text}</td>
                  <td className="px-5 py-3 tabular-nums">{r.rating ?? "–"}</td>
                  <td className="whitespace-nowrap px-5 py-3 text-muted">{formatDate(r.reviewed_on)}</td>
                  <td className="px-5 py-3 text-muted">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {page && page.total > LIMIT && (
            <div className="flex items-center justify-between border-t border-border px-5 py-3 text-sm">
              <span className="text-muted">
                {offset + 1}–{Math.min(offset + LIMIT, page.total)} of {page.total.toLocaleString()}
              </span>
              <div className="flex gap-2">
                <button className="btn btn-secondary btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                  Previous
                </button>
                <button className="btn btn-secondary btn-sm" disabled={offset + LIMIT >= page.total} onClick={() => setOffset(offset + LIMIT)}>
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function plural(n: number, word: string) {
  return `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
}

/* ------------------------------------------------------------------ changes */
function ChangesTab({ productId }: { productId: string }) {
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => setChanges(await api<Change[]>(`/v1/products/${productId}/changes`)), [productId]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    setError(null);
    try {
      await api(`/v1/products/${productId}/changes`, {
        method: "POST",
        json: {
          changed_on: f.get("changed_on"),
          aspects: String(f.get("aspects")).split(",").map((s) => s.trim()).filter(Boolean),
          description: f.get("description"),
        },
      });
      form.reset();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log the change.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
      <form onSubmit={onSubmit} className="card space-y-4 self-start p-5">
        <div>
          <div className="font-medium">Log a change you shipped</div>
          <p className="mt-0.5 text-sm text-muted">Fix verification will test whether complaints about these aspects fell afterwards.</p>
        </div>
        <div>
          <label htmlFor="c-date" className="label">
            Date shipped
          </label>
          <input id="c-date" name="changed_on" type="date" required className="input" />
        </div>
        <div>
          <label htmlFor="c-aspects" className="label">
            Aspects affected
          </label>
          <input id="c-aspects" name="aspects" required className="input" placeholder="battery life, charging case" />
          <p className="mt-1.5 text-xs text-muted">Comma separated.</p>
        </div>
        <div>
          <label htmlFor="c-desc" className="label">
            What changed
          </label>
          <textarea id="c-desc" name="description" required minLength={3} maxLength={1000} rows={3} className="input" placeholder="Switched to a new battery supplier from batch 14" />
        </div>
        <FormError message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Saving…" : "Log change"}
        </button>
      </form>

      <div>
        {changes && changes.length === 0 ? (
          <Empty title="No changes logged" body="When you fix something (supplier, packaging, firmware), log it here to measure whether it worked." />
        ) : (
          <ol className="card divide-y divide-border">
            {changes?.map((c) => (
              <li key={c.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{formatDate(c.changed_on)}</span>
                  <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted">Verification pending analysis</span>
                </div>
                <p className="mt-1 text-fg-2">{c.description}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {c.aspects.map((a) => (
                    <span key={a} className="rounded-md bg-surface-2 px-2 py-0.5 text-xs text-fg-2">
                      {a}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ insights */
function InsightsTab({ count }: { count: number }) {
  return (
    <div className="card p-6">
      <div className="font-medium">Insights are coming in the analysis release</div>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        This tab will show the ranked issue list, weekly trends per aspect, early-warning alerts and fix-verification results. Your{" "}
        {count.toLocaleString()} review{count === 1 ? "" : "s"} and logged changes are already stored, so history will be analysed as soon as it ships.
      </p>
    </div>
  );
}
