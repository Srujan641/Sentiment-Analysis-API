// Browser-side client for the /v1 API (proxied to FastAPI by next.config.ts).

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const item = d as { loc?: (string | number)[]; msg?: string };
        const field = (item.loc ?? []).filter((p) => p !== "body").join(".");
        const msg = (item.msg ?? "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join(" ");
  }
  return "";
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(path, {
      ...rest,
      headers: { Accept: "application/json", ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    const detail = describe((data as { detail?: unknown } | null)?.detail);
    if (res.status === 429 && !detail) throw new ApiError("Too many requests. Wait a moment and try again.", 429);
    throw new ApiError(detail || `Request failed (${res.status}).`, res.status);
  }
  return data as T;
}

// ---- types mirrored from app/platform/schemas.py ----
export type Me = {
  user: { id: string; email: string; name: string; role: string };
  organization: { id: string; name: string; account_type: "individual" | "organization"; plan: string };
};
export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};
export type Product = {
  id: string;
  name: string;
  brand: string | null;
  category: string | null;
  identifiers: Record<string, string>;
  links: string[];
  review_count: number;
  archived: boolean;
  created_at: string;
};
export type Change = { id: string; changed_on: string; aspects: string[]; description: string; created_at: string };
export type Review = {
  id: string;
  source: string;
  text: string;
  rating: number | null;
  reviewed_on: string | null;
  ingested_at: string;
};
export type IngestResult = {
  received: number;
  added: number;
  duplicates: number;
  rejected: number;
  remaining_this_month: number | null;
};
export type Meter = { used: number; limit: number | null };
export type Usage = {
  period: string;
  plan: string;
  products: Meter;
  reviews_ingested: Meter;
  reports_generated: Meter;
  rate_limit: string;
};

// ---- analysis reports (app/analysis/engine.py) ----
export type Quote = { text: string; review_id: string; rating: number | null; date: string | null; source: string };
export type AspectStat = {
  aspect: string;
  discovered: boolean;
  mentions: number;
  negative: number;
  positive: number;
  share: number;
  negative_share: number;
  negative_rate: number;
  rating_impact: number | null;
  quotes: Quote[];
  specific_issues?: { name: string; mentions: number; quotes: Quote[] }[];
};
export type FixResult = {
  requested: string;
  aspect: string | null;
  verdict: "improved" | "worse" | "no_significant_change" | "inconclusive" | "not_enough_data" | "unknown_aspect";
  before_rate?: number | null;
  after_rate?: number | null;
  relative_change?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  p_value?: number | null;
  reviews_before?: number;
  reviews_after?: number;
  method?: string;
  note?: string;
};
export type Report = {
  analysis_id: string;
  kind: "quick" | "full";
  generated_at: string;
  review_count: number;
  dated_reviews?: number;
  period?: { from: string | null; to: string | null };
  overall: {
    positive_share: number;
    negative_share: number;
    sentiment_score: number;
    average_rating: number | null;
    rated_reviews: number;
  } | null;
  lacking: AspectStat[];
  strengths: AspectStat[];
  trends?: { aspect: string; weeks: { week: string; reviews: number; negative: number }[] }[];
  fix_verification?: { change_id: string; changed_on: string; description: string; results: FixResult[] }[];
  alerts?: {
    aspect: string;
    first_seen: string;
    current_rate: number;
    baseline_rate: number;
    complaints: number;
    reviews: number;
    p_value: number;
    quotes: Quote[];
  }[];
  summary: string[];
  methodology?: Record<string, string | number>;
};
export type AnalysisRun = {
  id: string;
  product_id: string;
  kind: "quick" | "full";
  status: "queued" | "running" | "complete" | "failed";
  stage: string | null;
  error: string | null;
  review_count: number | null;
  created_at: string;
  finished_at: string | null;
  status_url: string;
  report_url: string;
};

// ---- review sources (app/platform/routes/sources.py) ----
export type ConnectorInfo = { name: string; label: string; available: boolean; requires: string | null };
export type SourceCandidate = {
  connector: string;
  ref: string;
  label: string;
  url: string | null;
  detail: string | null;
  allowed: boolean;
  reason: string | null;
};
export type Source = {
  id: string;
  connector: string;
  ref: string;
  label: string;
  url: string | null;
  last_collected_at: string | null;
  last_added: number | null;
  last_error: string | null;
};
export type CollectionRun = {
  id: string;
  status: "queued" | "running" | "complete" | "failed";
  stage: string | null;
  results: { label: string; connector: string; fetched?: number; added?: number; duplicates?: number; skipped_over_quota?: number; error?: string }[] | null;
  error: string | null;
  status_url: string;
};
