"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader, useSession } from "@/components/app/AppShell";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const { me } = useSession();
  const router = useRouter();

  async function logout() {
    await api("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/business/login");
  }

  const rows: [string, React.ReactNode][] = [
    ["Name", me.user.name],
    ["Email", me.user.email],
    ["Role", <span key="r" className="capitalize">{me.user.role}</span>],
    ["Organization", me.organization.name],
    ["Account type", <span key="t" className="capitalize">{me.organization.account_type}</span>],
    [
      "Plan",
      <span key="p" className="flex items-center gap-3">
        <span className="capitalize">{me.organization.plan}</span>
        <Link href="/pricing" className="text-sm text-link underline-offset-4 hover:underline">
          Compare plans
        </Link>
      </span>,
    ],
  ];

  return (
    <>
      <PageHeader title="Settings" />
      <dl className="card divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="grid gap-1 px-5 py-3.5 text-sm sm:grid-cols-[180px_1fr]">
            <dt className="text-muted">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-sm text-muted">
        To change your plan during the pilot, contact us. Self-serve billing is coming after the MVP.
      </p>
      <button className="btn btn-secondary mt-6" onClick={logout}>
        Log out
      </button>
    </>
  );
}
