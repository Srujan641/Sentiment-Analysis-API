"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/app/AppShell";
import { Empty, Modal, Notice, formatDate } from "@/components/app/ui";
import { Field, FormError } from "@/components/forms/Field";
import { api, ApiError, type Product } from "@/lib/api";

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setProducts(await api<Product[]>(`/v1/products${showArchived ? "?include_archived=true" : ""}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [showArchived]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Products"
        description="Each product collects reviews from all its sources."
        actions={
          <button className="btn btn-primary" onClick={() => setOpen(true)}>
            Add product
          </button>
        }
      />
      {error && <Notice tone="neg">{error}</Notice>}

      {products && products.length === 0 && !showArchived ? (
        <Empty
          title="No products yet"
          body="Add a product, then upload a review export or push reviews through the API."
          action={
            <button className="btn btn-primary" onClick={() => setOpen(true)}>
              Add your first product
            </button>
          }
        />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-medium">Product</th>
                <th className="px-5 py-3 font-medium">Category</th>
                <th className="px-5 py-3 text-right font-medium">Reviews</th>
                <th className="px-5 py-3 font-medium">Added</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(products ?? []).map((p) => (
                <tr key={p.id} className="hover:bg-surface-2">
                  <td className="px-5 py-3.5">
                    <Link href={`/app/products/${p.id}`} className="font-medium hover:underline">
                      {p.name}
                    </Link>
                    {p.brand && <span className="text-muted"> · {p.brand}</span>}
                    {p.archived && <span className="ml-2 rounded border border-border px-1.5 text-[11px] text-muted">Archived</span>}
                  </td>
                  <td className="px-5 py-3.5 text-fg-2">{p.category ?? "–"}</td>
                  <td className="px-5 py-3.5 text-right tabular-nums">{p.review_count.toLocaleString()}</td>
                  <td className="px-5 py-3.5 text-muted">{formatDate(p.created_at)}</td>
                </tr>
              ))}
              {!products && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-muted">
                    Loading…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <label className="mt-4 flex items-center gap-2 text-sm text-muted">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Show archived
      </label>

      <CreateProduct open={open} onClose={() => setOpen(false)} onCreated={load} />
    </>
  );
}

function CreateProduct({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const asin = String(f.get("asin") || "").trim();
    const appId = String(f.get("app_id") || "").trim();
    setBusy(true);
    setError(null);
    try {
      await api("/v1/products", {
        method: "POST",
        json: {
          name: f.get("name"),
          brand: f.get("brand") || null,
          category: f.get("category") || null,
          identifiers: { ...(asin ? { asin } : {}), ...(appId ? { app_id: appId } : {}) },
        },
      });
      (e.target as HTMLFormElement).reset();
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the product.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add product">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field id="p-name" name="name" label="Product name" required maxLength={200} placeholder="Earbuds X200" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="p-brand" name="brand" label="Brand" maxLength={120} />
          <Field id="p-category" name="category" label="Category" maxLength={120} placeholder="Audio" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="p-asin" name="asin" label="ASIN (optional)" maxLength={20} />
          <Field id="p-app" name="app_id" label="App ID (optional)" maxLength={200} hint="For app-store sources." />
        </div>
        <FormError message={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Adding…" : "Add product"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
