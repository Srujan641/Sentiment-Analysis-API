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
