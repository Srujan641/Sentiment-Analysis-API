"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader, useSession } from "@/components/app/AppShell";
import { Meter, Notice } from "@/components/app/ui";
import { api, type ApiKey, type Product, type Usage } from "@/lib/api";

type Data = { usage: Usage; products: Product[]; keys: ApiKey[] };

export default function OverviewPage() {
  const { me } = useSession();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api<Usage>("/v1/usage"), api<Product[]>("/v1/products"), api<ApiKey[]>("/v1/keys")])
      .then(([usage, products, keys]) => setData({ usage, products, keys }))
      .catch((e: Error) => setError(e.message));
  }, []);

  const firstName = me.user.name.split(" ")[0];
  const steps = data && [
    { done: data.products.length > 0, label: "Add your first product", href: "/app/products" },
    { done: data.products.some((p) => p.review_count > 0), label: "Upload or push reviews", href: data.products[0] ? `/app/products/${data.products[0].id}` : "/app/products" },
    { done: data.keys.some((k) => !k.revoked_at), label: "Create an API key", href: "/app/keys" },
  ];

  return (
    <>
      <PageHeader title={`Welcome, ${firstName}`} description={`${me.organization.name} · ${data?.usage.period ?? ""}`} />
      {error && <Notice tone="neg">{error}</Notice>}

      {steps && steps.some((s) => !s.done) && (
        <section className="card mb-6 p-5">
          <h2 className="font-semibold">Get started</h2>
          <ol className="mt-3 space-y-2">
            {steps.map((s, i) => (
              <li key={s.label} className="flex items-center gap-3 text-sm">
                <span
                  className={`flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                    s.done ? "border-pos-border bg-pos-bg text-pos" : "border-border-strong text-muted"
                  }`}
                  aria-hidden="true"
                >
                  {s.done ? "✓" : i + 1}
                </span>
                {s.done ? (
                  <span className="text-muted line-through">{s.label}</span>
                ) : (
                  <Link href={s.href} className="font-medium underline-offset-4 hover:underline">
                    {s.label}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {data ? (
          <>
            <Meter label="Active products" used={data.usage.products.used} limit={data.usage.products.limit} />
            <Meter label="Reviews this month" used={data.usage.reviews_ingested.used} limit={data.usage.reviews_ingested.limit} />
            <Meter label="Reports this month" used={data.usage.reports_generated.used} limit={data.usage.reports_generated.limit} />
          </>
        ) : (
          [0, 1, 2].map((i) => <div key={i} className="card h-[118px] animate-pulse" />)
        )}
      </div>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Products</h2>
          <Link href="/app/products" className="text-sm text-muted hover:text-fg">
            View all →
          </Link>
        </div>
        {data && data.products.length === 0 ? (
          <div className="card p-5 text-sm text-muted">No products yet.</div>
        ) : (
          <ul className="card divide-y divide-border">
            {data?.products.slice(0, 5).map((p) => (
              <li key={p.id}>
                <Link href={`/app/products/${p.id}`} className="flex items-center justify-between px-5 py-3.5 hover:bg-surface-2">
                  <span>
                    <span className="font-medium">{p.name}</span>
                    {p.brand && <span className="text-muted"> · {p.brand}</span>}
                  </span>
                  <span className="text-sm tabular-nums text-muted">{p.review_count.toLocaleString()} reviews</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-6 text-xs text-muted">Rate limit on your plan: {data?.usage.rate_limit.replace("/", " requests / ")}.</p>
    </>
  );
}
