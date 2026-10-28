import Link from "next/link";
import { SITE } from "@/lib/site";

export default function HomePage() {
  return (
    <>
      <Hero />
      <Problem />
      <Capabilities />
      <HowItWorks />
      <Sources />
      <Developers />
      <Responsible />
      <Faq />
      <FinalCta />
    </>
  );
}

/* ------------------------------------------------------------------ hero */
function Hero() {
  return (
    <section className="border-b border-border">
      <div className="container-page grid items-center gap-12 py-16 md:py-24 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <p className="eyebrow">Review intelligence for D2C brands</p>
          <h1 className="mt-4 text-[40px] font-semibold leading-[1.08] tracking-[-0.03em] text-balance sm:text-[52px]">
            Know what to fix next. Prove the fix worked.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-fg-2">
            {SITE.name} reads every review your customers write, on your store, app stores, YouTube and Reddit, and
            turns them into a ranked fix list, early warnings before ratings drop, and statistical proof that your
            changes worked.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup" className="btn btn-primary h-11 px-5">
              Start free
            </Link>
            <Link href="/docs" className="btn btn-secondary h-11 px-5">
              Read the API docs
            </Link>
          </div>
          <p className="mt-4 text-[13px] text-muted">Free plan, no card required. API key in under a minute.</p>
        </div>
        <FixVerificationCard />
      </div>
    </section>
  );
}

const WEEKS = [30, 32, 29, 33, 31, 34, 32, 22, 19, 18, 17, 18];
const CHANGE_AT = 7; // index of the first week after the change

function FixVerificationCard() {
  const w = 420;
  const h = 150;
  const max = 40;
  const x = (i: number) => 16 + (i * (w - 32)) / (WEEKS.length - 1);
  const y = (v: number) => h - 20 - (v / max) * (h - 36);
  const pts = WEEKS.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const cx = (x(CHANGE_AT - 1) + x(CHANGE_AT)) / 2;

  return (
    <div className="card p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)] sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="eyebrow">Fix verification</div>
          <div className="mt-1 font-medium">Earbuds X200 · battery life</div>
        </div>
        <span className="rounded-md border border-pos-border bg-pos-bg px-2.5 py-1 text-xs font-semibold tracking-wide text-pos">
          IMPROVED
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3 border-y border-border py-4">
        <Stat label="Before" value="31.6%" sub="of reviews" />
        <Stat label="After" value="18.4%" sub="of reviews" />
        <Stat label="Change" value="−42%" sub="95% CI −51 to −31" tone="pos" />
      </div>

      <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 w-full" role="img" aria-label="Weekly share of reviews complaining about battery life, falling after the logged change">
        {[0, 20, 40].map((v) => (
          <line key={v} x1="16" x2={w - 16} y1={y(v)} y2={y(v)} className="stroke-border" strokeWidth="1" />
        ))}
        <line x1={cx} x2={cx} y1="8" y2={h - 20} className="stroke-muted" strokeDasharray="3 4" strokeWidth="1" />
        <text x={cx + 6} y="16" className="fill-muted text-[10px]">
          New battery supplier
        </text>
        <polyline points={pts} fill="none" className="stroke-fg" strokeWidth="2" strokeLinejoin="round" />
        {WEEKS.map((v, i) => (
          <circle key={i} cx={x(i)} cy={y(v)} r="2.5" className={i >= CHANGE_AT ? "fill-pos" : "fill-fg"} />
        ))}
        <text x="16" y={h - 4} className="fill-muted text-[10px]">
          12 weeks
        </text>
      </svg>

      <p className="mt-3 text-[13px] text-muted">
        Segmented regression on 1,840 reviews, p = 0.003. <span className="italic">Example data.</span>
      </p>
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub: string; tone?: "pos" }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-0.5 text-2xl font-semibold tracking-tight tabular-nums ${tone === "pos" ? "text-pos" : ""}`}>
        {value}
      </div>
      <div className="text-xs text-muted">{sub}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ problem */
function Problem() {
  const items = [
    {
      title: "Reviews are scattered",
      body: "Your store, Amazon, app stores, YouTube comments and Reddit threads. Nobody reads all of them, so patterns are found late.",
    },
    {
      title: "Dashboards stop at “what”",
      body: "Topic and sentiment charts tell you customers mention the battery. They don't tell you whether last month's fix worked.",
    },
    {
      title: "Problems surface as lost stars",
      body: "A bad batch or courier issue shows up in your rating weeks after the first complaints, when returns are already rising.",
    },
  ];
  return (
    <section className="border-b border-border">
      <div className="container-page py-16 md:py-20">
        <SectionHead eyebrow="The problem" title="Brands hear customers too late, and can't tell if fixes land" />
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {items.map((i) => (
            <div key={i.title} className="card p-6">
              <h3 className="font-semibold">{i.title}</h3>
              <p className="mt-2 text-fg-2">{i.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ capabilities */
function Capabilities() {
  return (
    <section id="product" className="scroll-mt-16 border-b border-border">
      <div className="container-page py-16 md:py-20">
        <SectionHead
          eyebrow="What you get"
          title="Three answers no review dashboard gives you"
          lede="Every feature is backed by a statistical test or a measured backtest, not just a chart."
        />
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          <Capability
            n="01"
            title="What to fix first"
            body="Every review is split into aspects (battery, fit, delivery, packaging), scored, and grouped. Issues are ranked by how many customers raise them and how much they pull your rating down."
            example={
              <ul className="space-y-2 text-sm">
                <IssueRow name="Battery life" share={31} />
                <IssueRow name="Mic quality on calls" share={18} />
                <IssueRow name="Fit for small ears" share={9} />
              </ul>
            }
          />
          <Capability
            n="02"
            title="Warning before ratings drop"
            body="Each aspect's complaint rate is tracked against its own baseline. When one rises significantly, you get an alert with the first date of the rise and example reviews."
            example={
              <div className="rounded-lg border border-warn-border bg-warn-bg p-3 text-sm text-warn">
                <div className="font-semibold">Charging-case hinge</div>
                <div className="mt-0.5">Complaints 2% → 9% since 14 Mar. Rating not yet affected.</div>
              </div>
            }
          />
          <Capability
            n="03"
            title="Proof that your fix worked"
            body="Log a change you shipped: a new supplier, packaging, firmware. We test whether complaints about that aspect really fell, accounting for volume and trend, and report the effect with a confidence interval."
            example={
              <div className="flex items-center justify-between rounded-lg border border-pos-border bg-pos-bg p-3 text-sm text-pos">
                <span className="font-semibold">Battery life: improved</span>
                <span className="tabular-nums">−42%, p = 0.003</span>
              </div>
            }
          />
        </div>
        <p className="mt-6 text-[13px] text-muted">
          Examples are illustrative. Coming next: spec-gap analysis that compares your complaints with competitors&apos;
          specifications.
        </p>
      </div>
    </section>
  );
}

function Capability({ n, title, body, example }: { n: string; title: string; body: string; example: React.ReactNode }) {
  return (
    <div className="card flex flex-col p-6">
      <div className="font-mono text-xs text-muted">{n}</div>
      <h3 className="mt-2 text-lg font-semibold">{title}</h3>
      <p className="mt-2 flex-1 text-fg-2">{body}</p>
      <div className="mt-5">{example}</div>
    </div>
  );
}

function IssueRow({ name, share }: { name: string; share: number }) {
  return (
    <li>
      <div className="flex justify-between">
        <span>{name}</span>
        <span className="tabular-nums text-muted">{share}%</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-border">
        <div className="h-full rounded-full bg-neg" style={{ width: `${share * 2.5}%` }} />
      </div>
    </li>
  );
}

/* ------------------------------------------------------------------ how it works */
function HowItWorks() {
  const steps = [
    {
      title: "Connect your reviews",
      body: "Upload a CSV from your store or review app, push reviews from your backend, or connect public sources. Duplicates and personal data are removed automatically.",
    },
    {
      title: "We analyse every review",
      body: "A model fine-tuned on product reviews (95% accuracy on 10,000 held-out reviews) scores sentiment; aspects are extracted and grouped into issues; trends are tracked weekly.",
    },
    {
      title: "Act, then verify",
      body: "Fix the top issue, log the change, and watch the verification result. Alerts and reports arrive on the dashboard or by webhook.",
    },
  ];
  return (
    <section id="how" className="scroll-mt-16 border-b border-border">
      <div className="container-page py-16 md:py-20">
        <SectionHead eyebrow="How it works" title="From scattered reviews to a decision in three steps" />
        <ol className="mt-10 grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.title} className="card p-6">
              <div className="flex size-8 items-center justify-center rounded-full border border-border-strong text-sm font-semibold">
                {i + 1}
              </div>
              <h3 className="mt-4 font-semibold">{s.title}</h3>
              <p className="mt-2 text-fg-2">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ sources */
function Sources() {
  const sources: [string, string][] = [
    ["Your store or review app export", "Available"],
    ["Push API", "Available"],
    ["Apple App Store", "Coming"],
    ["Google Play", "Coming"],
    ["YouTube comments", "Coming"],
    ["Reddit", "Coming"],
    ["Amazon (your own listings, via Amazon's seller API)", "Planned"],
  ];
  return (
    <section id="sources" className="scroll-mt-16 border-b border-border">
      <div className="container-page grid gap-10 py-16 md:grid-cols-[1fr_1.2fr] md:py-20">
        <SectionHead
          eyebrow="Sources"
          title="Every channel, through the front door"
          lede="We use your own exports and official APIs. We don't scrape marketplaces whose terms forbid it, so the data you build decisions on won't disappear."
        />
        <ul className="card divide-y divide-border">
          {sources.map(([name, status]) => (
            <li key={name} className="flex items-center justify-between gap-4 px-5 py-3.5 text-sm">
              <span>{name}</span>
              <span
                className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${
                  status === "Available" ? "bg-pos-bg text-pos" : "bg-surface-2 text-muted"
                }`}
              >
                {status}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ developers */
function Developers() {
  return (
    <section className="border-b border-border">
      <div className="container-page grid items-center gap-10 py-16 md:grid-cols-2 md:py-20">
        <div>
          <SectionHead
            eyebrow="API-first"
            title="One key, a few calls"
            lede="Everything on the dashboard is available through the REST API, with per-plan rate limits and clear errors."
          />
          <Link href="/docs" className="btn btn-secondary mt-6">
            Read the quickstart
          </Link>
        </div>
        <pre className="card overflow-x-auto p-5 font-mono text-[12.5px] leading-6 text-fg-2">
{`# 1. Create a product
curl -X POST $API/v1/products \\
  -H "Authorization: Bearer rp_live_..." \\
  -d '{"name": "Earbuds X200", "brand": "Acme"}'

# 2. Push reviews (or upload a CSV)
curl -X POST $API/v1/products/{id}/reviews \\
  -d '{"reviews": [{"text": "Battery dies in 2 hours",
                    "rating": 2, "reviewed_on": "2026-09-03"}]}'

# 3. Log a change you shipped
curl -X POST $API/v1/products/{id}/changes \\
  -d '{"changed_on": "2026-09-01",
       "aspects": ["battery life"],
       "description": "New battery supplier"}'`}
        </pre>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ responsible */
function Responsible() {
  const points = [
    ["No reviewer personal data", "Names, emails, phone numbers and links are stripped before anything is stored."],
    ["Your data stays yours", "Every record is scoped to your organization. Deleted on request."],
    ["Grounded summaries", "Written summaries are generated only from extracted issues and real quotes, and every claim links to its reviews."],
    ["Built for India's DPDP Act", "Data minimisation and deletion by design."],
  ];
  return (
    <section id="responsible" className="scroll-mt-16 border-b border-border">
      <div className="container-page py-16 md:py-20">
        <SectionHead eyebrow="Responsible by design" title="Insight without collecting what you don't need" />
        <div className="mt-10 grid gap-x-10 gap-y-6 sm:grid-cols-2">
          {points.map(([t, b]) => (
            <div key={t} className="border-l-2 border-border-strong pl-4">
              <h3 className="font-semibold">{t}</h3>
              <p className="mt-1 text-fg-2">{b}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ FAQ */
function Faq() {
  const faqs = [
    [
      "How is this different from a review dashboard?",
      "Dashboards show topics and sentiment. ReviewPulse also tells you whether a change you shipped reduced complaints, and warns you when a new problem starts, before it reaches your star rating.",
    ],
    [
      "Do you scrape Amazon or Flipkart?",
      "No. Their terms prohibit it. Upload your own exports, use the push API, or (planned) connect Amazon's official seller API for your own listings.",
    ],
    [
      "Do you handle Hinglish reviews?",
      "Code-mixed Hindi-English support is on the roadmap for the analysis release. English is supported today.",
    ],
    [
      "How many reviews do I need for fix verification?",
      "It depends on how often an aspect is mentioned. When there isn't enough data for a reliable answer, the result says “not enough data” and tells you how many more reviews are needed, rather than guessing.",
    ],
    ["Can I try it without a card?", "Yes. The Free plan needs only an email."],
  ];
  return (
    <section className="border-b border-border">
      <div className="container-page grid gap-10 py-16 md:grid-cols-[1fr_1.6fr] md:py-20">
        <SectionHead eyebrow="FAQ" title="Questions brands ask first" />
        <div className="divide-y divide-border border-y border-border">
          {faqs.map(([q, a]) => (
            <details key={q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                {q}
                <span className="text-muted transition-transform group-open:rotate-45" aria-hidden="true">
                  +
                </span>
              </summary>
              <p className="mt-2 text-fg-2">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ CTA */
function FinalCta() {
  return (
    <section>
      <div className="container-page py-16 md:py-20">
        <div className="card flex flex-col items-start justify-between gap-6 p-8 md:flex-row md:items-center md:p-10">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Find out what your customers want fixed</h2>
            <p className="mt-2 text-fg-2">Create a free account, upload a review export, and see your first issues in minutes.</p>
          </div>
          <div className="flex gap-3">
            <Link href="/signup" className="btn btn-primary h-11 px-5">
              Start free
            </Link>
            <Link href="/pricing" className="btn btn-secondary h-11 px-5">
              See pricing
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function SectionHead({ eyebrow, title, lede }: { eyebrow: string; title: string; lede?: string }) {
  return (
    <div className="max-w-2xl">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-[28px] font-semibold leading-tight tracking-[-0.02em] text-balance sm:text-[32px]">{title}</h2>
      {lede && <p className="mt-3 text-fg-2">{lede}</p>}
    </div>
  );
}
