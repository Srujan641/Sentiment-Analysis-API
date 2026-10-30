# ReviewPulse: Product Requirements

> Working name. Check trademark and domain availability before any public launch.

| | |
|---|---|
| Status | Draft v1, MVP scope |
| Owner | Srujan P V |
| Last updated | 2026-10-28 |

---

## 1. Summary

ReviewPulse turns product reviews from every channel into decisions. Existing review-analytics tools
answer *"what are customers saying?"* ReviewPulse also answers three questions those tools don't:

1. **Did our fix work?** (fix verification) A brand logs a product change. ReviewPulse measures whether
   complaints about the affected aspect actually dropped, with a statistical test rather than a chart.
2. **What will hurt us next?** (early warning) ReviewPulse detects a newly emerging problem from a
   change in one aspect's complaint rate, before the star rating falls.
3. **What should version 2 have?** (spec-gap analysis, phase 2) ReviewPulse links complaints to product
   specifications and to competitors, producing concrete targets for the next version.

Delivery is self-serve and API-first: sign up, create an API key, send products or reviews, receive reports.

## 2. Problem

- Indian D2C brands sell on their own site plus Amazon, Flipkart and quick-commerce apps. Their reviews are
  scattered across channels and often written in Hinglish.
- Enterprise review-analytics platforms (Revuze, Wonderflow, Unwrap and others) are sold through demo
  calls and priced for large brands. Tools bundled with review apps (for example Yotpo Insights) analyse
  only the reviews collected through that app.
- Every tool reports *topics and sentiment*. None tells a brand whether the change it shipped last month
  worked, or warns it before a defect reaches the star rating.

## 3. Users

| Persona | Who | Need | Plan |
|---|---|---|---|
| **Brand operator** (primary) | Founder, product or CX lead at a D2C brand with 5–200 SKUs | A ranked fix list, proof that fixes worked, early warnings | Starter / Growth |
| **App product manager** | PM at an app company | The same, from app-store reviews | Starter / Growth |
| **Individual** | Small seller, creator, student, shopper | "What is this product lacking?" | Free |
| **Developer** | Engineer integrating the API | Clear docs, predictable API, webhooks | Any |

## 4. Scope

### In scope (MVP)
Accounts and organizations, API keys, plans and quotas, products, review ingestion (upload, push API and
public connectors), aspect-based sentiment, complaint grouping, the "what's lacking" ranking, trends,
**fix verification**, **early warning**, quick and full reports (JSON, PDF, dashboard), async jobs,
webhooks, the marketing website and the web app.

### Out of scope (MVP)
Spec-gap analysis (phase 2), the Amazon SP-API connector (phase 2: needs Amazon developer approval),
Shopify app-store listing, billing and payments (plans are assigned manually during pilots),
replying to reviews, any scraping of sites whose terms forbid it.

## 5. Functional requirements

Priority: **P0** is required for the MVP demo, **P1** is required for pilot customers, **P2** comes after the MVP.

### 5.1 Accounts and access
| ID | Requirement | P |
|---|---|---|
| ACC-1 | Sign up with email and password; choose *individual* or *organization*. Passwords hashed with Argon2. | P0 |
| ACC-2 | Log in and out on the website with a secure, HTTP-only session cookie. | P0 |
| ACC-3 | An organization has members with roles *owner* and *member*. | P1 |
| ACC-4 | Create, list, name and revoke API keys. The full key is shown **once**; only a SHA-256 hash and a short display prefix are stored. | P0 |
| ACC-5 | Every API request authenticates with `Authorization: Bearer <key>` or `X-API-Key`. | P0 |
| ACC-6 | Each account has a plan (Free, Starter, Growth, Enterprise) that sets its quotas. | P0 |
| ACC-7 | Quotas are enforced per month (products, reports, reviews ingested) and per minute (rate limit). Exceeding one returns `429` with a clear message. | P0 |
| ACC-8 | `GET /v1/usage` and the dashboard show usage against quota. | P0 |
| ACC-9 | Email verification and password reset. | P1 |

### 5.2 Products and changes
| ID | Requirement | P |
|---|---|---|
| PRD-1 | Create a product with name, brand, category, optional identifiers (ASIN, GTIN, app ID) and source links. | P0 |
| PRD-2 | List, update and archive products. | P0 |
| PRD-3 | **Log a product change**: date, affected aspect(s), description (for example "new battery supplier, batch 14"). Changes drive fix verification. | P0 |

### 5.3 Review ingestion
| ID | Requirement | P |
|---|---|---|
| ING-1 | Upload reviews as CSV or JSON (text, rating, date, optional source and ID). | P0 |
| ING-2 | Push reviews through `POST /v1/products/{id}/reviews` in batches of up to 1,000. | P0 |
| ING-3 | Connector: Apple App Store public reviews feed. | P1 |
| ING-4 | Connector: Google Play reviews. | P1 |
| ING-5 | Connector: YouTube Data API comments on given videos, or on videos found by search. | P1 |
| ING-6 | Connector: Reddit API posts and comments matching the product. | P1 |
| ING-7 | Connector: web pages found through a search API and read with Firecrawl, **only** where robots.txt and the site's terms allow. | P2 |
| ING-8 | Cleaning: exact and near-duplicate removal, language detection, spam filtering, and **removal of personal data** (reviewer names, emails, phone numbers are never stored). | P0 |
| ING-9 | Every review records its source, original date and ingestion date. | P0 |
| ING-10 | Connectors fail independently; a report lists which sources succeeded. | P1 |

### 5.4 Analysis
| ID | Requirement | P |
|---|---|---|
| ANA-1 | Overall sentiment per review, using the project's fine-tuned DistilBERT (94.97% accuracy). | P0 |
| ANA-2 | Aspect extraction and per-aspect sentiment (aspect-based sentiment analysis). | P0 |
| ANA-3 | Group similar aspect phrases into one issue ("battery dies fast" and "poor battery life" become *battery life*). | P0 |
| ANA-4 | **What's-lacking ranking**: issues ranked by share of reviews × negativity × estimated impact on rating. | P0 |
| ANA-5 | Trends per aspect by week. | P0 |
| ANA-6 | Hinglish (code-mixed Hindi-English) reviews are handled. | P1 |
| ANA-7 | Suspected fake or duplicate reviews are excluded and counted in the report. | P1 |

### 5.5 Novelty features
| ID | Requirement | P |
|---|---|---|
| FIX-1 | **Fix verification**: for each logged change, compare the affected aspect's negative-mention rate before and after the change date. | P0 |
| FIX-2 | The result is one of *improved*, *no significant change*, *worse* or *not enough data*, with effect size, confidence interval, p-value and the sample sizes used. | P0 |
| FIX-3 | The test accounts for review volume and the aspect's existing trend (segmented regression / interrupted time series), and states the minimum number of reviews needed. | P0 |
| EWS-1 | **Early warning**: monitor each aspect's complaint rate over time and raise an alert when it rises significantly above its own baseline. | P0 |
| EWS-2 | An alert includes the aspect, current vs. baseline rate, the first date of the rise, and example reviews. | P0 |
| EWS-3 | Alerts are delivered on the dashboard and by webhook; email in P1. | P0 |
| SPEC-1 | Spec-gap analysis against competitor products. | P2 |

### 5.6 Reports
| ID | Requirement | P |
|---|---|---|
| REP-1 | **Quick report** (all plans): overall score, top 5 issues with share, negativity and an example quote each, top 3 strengths. | P0 |
| REP-2 | **Full report** (paid plans): everything in quick, plus every aspect with trend, breakdown by source and rating, fix-verification results, active alerts, excluded reviews, recommendations. | P0 |
| REP-3 | Every claim in a report links to the reviews it came from. | P0 |
| REP-4 | The written summary is generated **only** from extracted facts and real quotes. The LLM never sees the open web, and a summary that cites an issue not in the data is rejected. | P0 |
| REP-5 | Formats: JSON (API), web page (dashboard), PDF. | P0 (PDF P1) |
| REP-6 | Reports are versioned; re-running keeps history. | P1 |

### 5.7 Jobs and integration
| ID | Requirement | P |
|---|---|---|
| JOB-1 | Long work (collection, analysis) runs as background jobs: `202 Accepted` + job ID, a status endpoint, and stages (queued → collecting → analysing → done / failed). | P0 |
| JOB-2 | Webhooks for `report.ready`, `alert.raised` and `job.failed`, signed with HMAC-SHA256. | P1 |
| JOB-3 | Scheduled refresh per product (weekly on Starter, daily on Growth). | P1 |

### 5.8 Website
| ID | Requirement | P |
|---|---|---|
| WEB-1 | Public pages: home (pitch), product (features), pricing, API docs, sign up, log in. | P0 |
| WEB-2 | App: dashboard overview, products list, product detail (issues, trends, changes, fix verification, alerts), API keys, usage, settings. | P0 |
| WEB-3 | Works at phone width; light and dark mode; meets WCAG AA contrast. | P0 |
| WEB-4 | Professional, neutral visual style; no decorative gradients. | P0 |

## 6. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Quick report latency, for a product with ≤ 2,000 reviews already ingested | < 60 s |
| NFR-2 | API read endpoints | p95 < 300 ms |
| NFR-3 | Ingestion throughput per worker | ≥ 100 reviews/s analysed |
| NFR-4 | Availability (once deployed) | 99.5% monthly |
| NFR-5 | Security | API keys and passwords stored only as hashes; HTTPS only; per-key rate limits; tenants can never read each other's data (enforced in every query and covered by tests) |
| NFR-6 | Privacy | No reviewer personal data stored; data deletion on request; compliant with India's DPDP Act 2023 |
| NFR-7 | Cost | Infrastructure + LLM cost per full report measured and reported; target < ₹5 |
| NFR-8 | Observability | Prometheus metrics, structured logs with request IDs, job and connector error rates |
| NFR-9 | Quality | Automated tests for every endpoint and connector; CI must pass before merge |

## 7. Data sources policy

| Source | Access | Allowed |
|---|---|---|
| Customer's own reviews (upload or push) | Provided by the owner | ✅ |
| Apple App Store | Public customer-reviews feed | ✅ |
| Google Play | Public review pages via a maintained client library | ✅ within rate limits |
| YouTube | Official Data API (key, daily quota) | ✅ |
| Reddit | Official API (OAuth) | ✅ under Reddit's terms |
| Amazon (the seller's own products) | Official SP-API Customer Feedback API, with seller authorization | ✅ phase 2 |
| Other websites | Search API + Firecrawl, respecting robots.txt and terms | ✅ case by case |
| Amazon, Flipkart, Myntra product pages (direct scraping) | Prohibited by their terms | ❌ |

## 8. Success metrics

### Model and novelty (measured offline, reported in the project)
| Metric | Method | Target |
|---|---|---|
| Aspect-sentiment F1 | SemEval-2014 restaurant/laptop benchmarks; a Hinglish benchmark from published research | Report vs. published baselines |
| Early-warning lead time | Backtest on Amazon Reviews 2023: days between our alert and a sustained ≥ 0.3-star drop in the 30-day average rating | Median ≥ 7 days |
| Early-warning precision | Share of alerts followed by a real rating drop or confirmed issue | ≥ 60% |
| Fix-verification validity | Simulated changes with known effects injected into real review streams: detection power and false-positive rate | Power ≥ 0.8 at a 30% reduction; false positives ≤ 5% |

### Business (measured with pilots)
| Metric | Target |
|---|---|
| Pilot brands onboarded with their own data | 3–5 |
| Time from signup to first report | < 10 minutes |
| Pilots who say they would pay | ≥ 2 |

## 9. Plans

| | Free | Starter | Growth | Enterprise |
|---|---|---|---|---|
| Price (hypothesis) | ₹0 | ₹2,999/mo | ₹9,999/mo | Custom |
| Products | 1 | 5 | 25 | Unlimited |
| Reports / month | 3 (quick) | 50 | 300 | Unlimited |
| Reviews ingested / month | 2,000 | 25,000 | 200,000 | Unlimited |
| Full reports, fix verification, early warning | – | ✅ | ✅ | ✅ |
| Webhooks, daily refresh | – | – | ✅ | ✅ |
| API rate limit | 30/min | 120/min | 300/min | Custom |

## 10. Architecture (MVP)

```
Website (Next.js) ──session──┐
Customers' code ──API key────┤
                             ▼
                    FastAPI (this repo)
                    accounts · keys · quotas · products · reports
                             │
          Postgres ◄─────────┼─────────► Redis job queue
                             │                 │
                             │          Workers: collect → clean →
                             │          analyse (DistilBERT + ABSA +
                             │          grouping) → fix verification →
                             │          early warning → summary (LLM)
                             ▼
                    Reports · alerts · webhooks · /metrics
```

Development uses SQLite and in-process jobs; production uses Postgres and Redis. The code is the same.

## 11. Milestones

| Weeks | Milestone | Acceptance |
|---|---|---|
| 1–2 | Platform core + website shell | Sign up, create a key, call the API, see usage on the dashboard |
| 3–4 | Ingestion: upload, push, app stores, YouTube, Reddit; cleaning | One product → reviews from ≥ 3 sources, cleaned |
| 5–6 | Aspect analysis, grouping, what's-lacking ranking, Hinglish | ABSA F1 reported on benchmarks |
| 6–7 | **Fix verification + early warning**, including the backtest | Lead time and false-positive rate reported |
| 7–8 | Reports (JSON, web, PDF), webhooks, app pages | A full report for a real product |
| 9 | Scheduled refresh, cost per report, monitoring | Cost per report reported |
| 10 | Deploy on free tiers, pilot onboarding, pitch deck | Public URL; pilots running |

## 12. Risks

| Risk | Mitigation |
|---|---|
| Public sources give too few reviews for small brands | Owner uploads are the primary data; public connectors add to them |
| Too few reviews for a statistical result | FIX-3 and EWS report "not enough data" instead of guessing |
| Free tiers change or run out | Quotas, caching, and an LLM call only once per report |
| LLM summaries invent claims | REP-3 and REP-4: grounded summaries, with claims checked against the extracted issues |
| A competitor copies the features | The moat is category benchmarks built from aggregated, anonymized data across customers |
