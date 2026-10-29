import type { Metadata } from "next";
import Link from "next/link";
import { PERSONAL_PLANS, PLANS } from "@/lib/site";

export const metadata: Metadata = { title: "Pricing" };

export default function PricingPage() {
  return (
    <div className="container-page py-16 md:py-20">
      <div className="mx-auto max-w-2xl text-center">
        <p className="eyebrow">Pricing</p>
        <h1 className="mt-3 text-[36px] font-semibold tracking-[-0.025em] sm:text-[44px]">Start free. Pay when it pays.</h1>
        <p className="mt-4 text-lg text-fg-2">Simple monthly plans in rupees. Prices exclude GST.</p>
      </div>

      <h2 className="mt-14 text-lg font-semibold">For shoppers</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {PERSONAL_PLANS.map((p) => (
          <div key={p.id} className="card flex flex-col p-6">
            <h3 className="font-semibold">{p.name}</h3>
            <div className="mt-4 flex items-baseline gap-1.5">
              <span className="text-[34px] font-semibold tracking-tight tabular-nums">{p.price}</span>
              <span className="text-sm text-muted">{p.period}</span>
            </div>
            <p className="mt-2 text-sm text-fg-2">{p.blurb}</p>
            <Link href="/signup" className="btn btn-secondary mt-5">
              {p.cta}
            </Link>
            <ul className="mt-6 space-y-2.5 text-sm text-fg-2">
              {p.features.map((f) => (
                <li key={f}>✓ {f}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <h2 className="mt-14 text-lg font-semibold">For brands</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {PLANS.map((p) => (
          <div key={p.id} className={`card flex flex-col p-6 ${p.highlight ? "border-fg ring-1 ring-fg" : ""}`}>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">{p.name}</h2>
              {p.highlight && (
                <span className="rounded-md bg-accent px-2 py-0.5 text-[11px] font-semibold tracking-wide text-accent-fg">
                  POPULAR
                </span>
              )}
            </div>
            <div className="mt-4 flex items-baseline gap-1.5">
              <span className="text-[34px] font-semibold tracking-tight tabular-nums">{p.price}</span>
              {p.period && <span className="text-sm text-muted">{p.period}</span>}
            </div>
            <p className="mt-2 min-h-[48px] text-sm text-fg-2">{p.blurb}</p>
            <Link
              href={p.id === "enterprise" ? "mailto:hello@example.com" : "/business/signup"}
              className={`btn mt-5 ${p.highlight ? "btn-primary" : "btn-secondary"}`}
            >
              {p.cta}
            </Link>
            <ul className="mt-6 space-y-2.5 text-sm">
              {p.features.map((f) => (
                <li key={f} className="flex gap-2.5">
                  <svg viewBox="0 0 16 16" className="mt-1 size-3.5 shrink-0 text-fg" aria-hidden="true">
                    <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="text-fg-2">{f}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-14 max-w-3xl">
        <h2 className="text-lg font-semibold">What counts toward limits</h2>
        <dl className="mt-4 divide-y divide-border border-y border-border text-sm">
          {[
            ["Products", "Active products. Archive one to free its slot; its history is kept."],
            ["Reviews", "New, unique reviews ingested in the calendar month. Duplicates are free."],
            ["Reports", "Quick or full reports generated in the calendar month."],
            ["Rate limit", "API requests per minute, per key. Exceeding it returns 429 with a Retry-After header."],
          ].map(([t, d]) => (
            <div key={t} className="grid gap-1 py-3 sm:grid-cols-[160px_1fr]">
              <dt className="font-medium">{t}</dt>
              <dd className="text-fg-2">{d}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
