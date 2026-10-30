import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "API quickstart" };

const SECTIONS = [
  { id: "auth", title: "Authentication" },
  { id: "products", title: "Products" },
  { id: "reviews", title: "Reviews" },
  { id: "changes", title: "Product changes" },
  { id: "usage", title: "Usage and limits" },
  { id: "errors", title: "Errors" },
];

export default function DocsPage() {
  return (
    <div className="container-page grid gap-10 py-12 md:grid-cols-[200px_1fr] md:py-16">
      <aside className="md:sticky md:top-24 md:self-start">
        <p className="eyebrow">Quickstart</p>
        <nav className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm md:flex-col" aria-label="Docs sections">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="text-fg-2 hover:text-fg">
              {s.title}
            </a>
          ))}
          <Link href="/api-reference" className="text-fg-2 hover:text-fg">
            Full API reference ↗
          </Link>
        </nav>
      </aside>

      <article className="min-w-0 max-w-3xl">
        <h1 className="text-[34px] font-semibold tracking-[-0.025em]">API quickstart</h1>
        <p className="mt-3 text-lg text-fg-2">
          The REST API lives under <Code>/v1</Code>. Requests and responses are JSON. Set <Code>$API</Code> to your
          ReviewPulse URL.
        </p>

        <Section id="auth" title="Authentication">
          <p>
            Create a key on the{" "}
            <Link href="/app/keys" className="text-link underline-offset-4 hover:underline">
              API keys
            </Link>{" "}
            page. The full key is shown once; we store only a hash. Send it on every request:
          </p>
          <Pre>{`Authorization: Bearer rp_live_...
# or
X-API-Key: rp_live_...`}</Pre>
        </Section>

        <Section id="products" title="Products">
          <Pre>{`curl -X POST $API/v1/products \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"name": "Earbuds X200", "brand": "Acme", "category": "Audio",
       "identifiers": {"asin": "B0XXXXXXX"}}'`}</Pre>
          <p>
            Also: <Code>GET /v1/products</Code>, <Code>GET /v1/products/{"{id}"}</Code>, <Code>PATCH</Code> to update,
            and <Code>DELETE</Code> to archive (history is kept and the plan slot is freed).
          </p>
        </Section>

        <Section id="reviews" title="Reviews">
          <p>Push up to 1,000 reviews per request:</p>
          <Pre>{`curl -X POST $API/v1/products/$ID/reviews \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"source": "shopify",
       "reviews": [{"text": "Battery dies in 2 hours", "rating": 2,
                    "reviewed_on": "2026-09-03", "external_id": "r-1029"}]}'`}</Pre>
          <p>Or upload a CSV, JSON or JSONL export (up to 10 MB). Columns are matched by common names:</p>
          <Pre>{`curl -X POST $API/v1/products/$ID/reviews/upload \\
  -H "Authorization: Bearer $KEY" -F "file=@reviews.csv"`}</Pre>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              Text: <Code>text</Code>, <Code>review</Code>, <Code>content</Code>, <Code>body</Code>, <Code>comment</Code>
            </li>
            <li>
              Rating (0–5): <Code>rating</Code>, <Code>stars</Code>, <Code>score</Code>
            </li>
            <li>
              Date: <Code>date</Code>, <Code>review_date</Code>, <Code>created_at</Code> (ISO, DD/MM/YYYY or Unix time)
            </li>
          </ul>
          <p>
            The response reports how many reviews were added, skipped as duplicates, or rejected as empty. Emails,
            phone numbers and links are removed before storage.
          </p>
          <Pre>{`{"received": 4, "added": 2, "duplicates": 1, "rejected": 1,
 "remaining_this_month": 1998}`}</Pre>
        </Section>

        <Section id="changes" title="Product changes">
          <p>
            Log every change you ship that should affect customers. Fix verification tests whether complaints about the
            named aspects fell after <Code>changed_on</Code>.
          </p>
          <Pre>{`curl -X POST $API/v1/products/$ID/changes \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"changed_on": "2026-09-01", "aspects": ["battery life"],
       "description": "Switched to new battery supplier (batch 14)"}'`}</Pre>
        </Section>

        <Section id="usage" title="Usage and limits">
          <Pre>{`curl $API/v1/usage -H "Authorization: Bearer $KEY"`}</Pre>
          <p>
            Every response includes <Code>X-RateLimit-Limit</Code> and <Code>X-RateLimit-Remaining</Code>. See{" "}
            <Link href="/pricing" className="text-link underline-offset-4 hover:underline">
              pricing
            </Link>{" "}
            for plan limits.
          </p>
        </Section>

        <Section id="errors" title="Errors">
          <p>
            Errors return a JSON body with a <Code>detail</Code> message.
          </p>
          <table className="mt-2 w-full text-sm">
            <tbody className="divide-y divide-border border-y border-border">
              {[
                ["401", "Missing, invalid or revoked API key"],
                ["403", "Action requires a logged-in user (for example, managing keys)"],
                ["404", "Not found, or belongs to another account"],
                ["413", "Upload too large"],
                ["422", "Invalid input; detail names the field"],
                ["429", "Rate limit or monthly quota reached; see Retry-After"],
              ].map(([c, d]) => (
                <tr key={c}>
                  <td className="py-2.5 pr-6 font-mono">{c}</td>
                  <td className="py-2.5 text-fg-2">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </article>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-12 scroll-mt-24 space-y-3 text-fg-2">
      <h2 className="text-xl font-semibold text-fg">{title}</h2>
      {children}
    </section>
  );
}

function Pre({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-border bg-surface p-4 font-mono text-[12.5px] leading-6 text-fg-2">
      {children}
    </pre>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px] text-fg">{children}</code>;
}
