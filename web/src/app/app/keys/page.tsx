"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/app/AppShell";
import { Empty, Modal, Notice, formatDate } from "@/components/app/ui";
import { FormError } from "@/components/forms/Field";
import { api, ApiError, type ApiKey } from "@/lib/api";

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => setKeys(await api<ApiKey[]>("/v1/keys")), []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<ApiKey & { key: string }>("/v1/keys", { method: "POST", json: { name: name.trim() || "Default key" } });
      setCreated(res.key);
      setCopied(false);
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the key.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(k: ApiKey) {
    if (!confirm(`Revoke “${k.name}”? Programs using it will stop working immediately.`)) return;
    await api(`/v1/keys/${k.id}`, { method: "DELETE" });
    await load();
  }

  async function copy() {
    if (!created) return;
    await navigator.clipboard.writeText(created);
    setCopied(true);
  }

  const active = keys?.filter((k) => !k.revoked_at) ?? [];
  const revoked = keys?.filter((k) => k.revoked_at) ?? [];

  return (
    <>
      <PageHeader title="API keys" description="Keys let your code call the API. Treat them like passwords." />

      <form onSubmit={create} className="card mb-6 flex flex-wrap items-end gap-3 p-5">
        <div className="min-w-[220px] flex-1">
          <label htmlFor="key-name" className="label">
            Key name
          </label>
          <input id="key-name" className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Production server" />
        </div>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create key"}
        </button>
        <div className="w-full">
          <FormError message={error} />
        </div>
      </form>

      {keys && keys.length === 0 ? (
        <Empty title="No API keys" body="Create a key to call the API from your code or scripts." />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Key</th>
                <th className="px-5 py-3 font-medium">Created</th>
                <th className="px-5 py-3 font-medium">Last used</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {[...active, ...revoked].map((k) => (
                <tr key={k.id} className={k.revoked_at ? "text-muted" : ""}>
                  <td className="px-5 py-3.5 font-medium">{k.name}</td>
                  <td className="px-5 py-3.5 font-mono text-[13px]">{k.prefix}••••••••</td>
                  <td className="px-5 py-3.5">{formatDate(k.created_at)}</td>
                  <td className="px-5 py-3.5">{k.last_used_at ? formatDate(k.last_used_at) : "Never"}</td>
                  <td className="px-5 py-3.5 text-right">
                    {k.revoked_at ? (
                      <span className="text-xs">Revoked</span>
                    ) : (
                      <button className="text-sm font-medium text-neg hover:underline" onClick={() => revoke(k)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={created !== null} onClose={() => setCreated(null)} title="Your new API key">
        <Notice tone="warn">Copy it now. For your security, we won&apos;t show it again.</Notice>
        <div className="mt-4 flex gap-2">
          <code className="min-w-0 flex-1 break-all rounded-lg border border-border bg-surface-2 px-3 py-2.5 font-mono text-[13px]">{created}</code>
          <button className="btn btn-secondary shrink-0" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <div className="mt-5 flex justify-end">
          <button className="btn btn-primary" onClick={() => setCreated(null)}>
            Done
          </button>
        </div>
      </Modal>
    </>
  );
}
