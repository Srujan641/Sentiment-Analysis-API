"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { LogoMark } from "@/components/Logo";
import { api, ApiError, type Me } from "@/lib/api";
import { SITE } from "@/lib/site";

type Session = { me: Me; refresh: () => Promise<void> };
const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside AppShell");
  return ctx;
}

const NAV = [
  { href: "/app", label: "Overview", icon: "M3 12 12 4l9 8M5 10v10h14V10" },
  { href: "/app/products", label: "Products", icon: "M4 7l8-4 8 4v10l-8 4-8-4V7Zm0 0 8 4 8-4M12 11v10" },
  { href: "/app/keys", label: "API keys", icon: "M15 7a4 4 0 1 1-3.9 5H3v3h3v3h3v-3h2.1A4 4 0 0 1 15 7Z" },
  { href: "/app/settings", label: "Settings", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM4 12h2m12 0h2M12 4v2m0 12v2" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);

  const refresh = useCallback(async () => {
    try {
      const m = await api<Me>("/v1/auth/me");
      // The business dashboard is for business accounts; personal accounts have their own.
      if (m.organization.account_type !== "organization") return router.replace("/me");
      setMe(m);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.replace("/business/login");
    }
  }, [router]);

  useEffect(() => {
    // Initial session fetch; setMe happens after the await, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function logout() {
    await api("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/business/login");
  }

  if (!me) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted" aria-live="polite">
        Loading your workspace…
      </div>
    );
  }

  const isActive = (href: string) => (href === "/app" ? pathname === "/app" : pathname.startsWith(href));

  return (
    <SessionContext.Provider value={{ me, refresh }}>
      <div className="flex flex-1 flex-col md:flex-row">
        <aside className="border-b border-border bg-surface md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:border-r md:border-b-0">
          <div className="flex h-14 items-center gap-2.5 px-4 font-semibold md:h-16 md:px-5">
            <LogoMark className="size-6" />
            {SITE.name}
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:px-3 md:pb-0" aria-label="App">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={isActive(n.href) ? "page" : undefined}
                className={`flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive(n.href) ? "bg-surface-2 text-fg" : "text-muted hover:bg-surface-2 hover:text-fg"
                }`}
              >
                <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true">
                  <path d={n.icon} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="hidden px-5 pt-6 md:block">
            <div className="truncate text-sm font-medium">{me.organization.name}</div>
            <div className="truncate text-xs text-muted">{me.user.email}</div>
            <div className="mt-2 flex items-center gap-2">
              <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] font-medium capitalize text-fg-2">
                {me.organization.plan} plan
              </span>
              <button onClick={logout} className="text-xs text-muted hover:text-fg">
                Log out
              </button>
            </div>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <div className="mx-auto max-w-[1040px]">{children}</div>
        </main>
      </div>
    </SessionContext.Provider>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
