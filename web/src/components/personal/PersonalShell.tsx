"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { LogoMark } from "@/components/Logo";
import { api, ApiError, type Me } from "@/lib/api";
import { SITE } from "@/lib/site";

const Ctx = createContext<Me | null>(null);
export const usePersonal = () => {
  const me = useContext(Ctx);
  if (!me) throw new Error("usePersonal must be used inside PersonalShell");
  return me;
};

export function PersonalShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  const load = useCallback(async () => {
    try {
      const m = await api<Me>("/v1/auth/me");
      if (m.organization.account_type === "organization") return router.replace("/app");
      setMe(m);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function logout() {
    await api("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  if (!me) return <div className="flex flex-1 items-center justify-center text-sm text-muted">Loading…</div>;

  return (
    <Ctx.Provider value={me}>
      <header className="border-b border-border bg-surface">
        <div className="container-page flex h-14 items-center gap-6">
          <Link href="/me" className="flex items-center gap-2.5 font-semibold">
            <LogoMark className="size-6" />
            {SITE.name}
          </Link>
          <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] font-medium text-muted">Personal</span>
          <div className="ml-auto flex items-center gap-4 text-sm">
            <span className="hidden text-muted sm:inline">{me.user.email}</span>
            <button onClick={logout} className="text-muted hover:text-fg">
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="container-page flex-1 py-8">{children}</main>
    </Ctx.Provider>
  );
}
