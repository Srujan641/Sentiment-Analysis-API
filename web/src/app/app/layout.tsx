import type { Metadata } from "next";
import { Suspense } from "react";
import { AppShell } from "@/components/app/AppShell";

export const metadata: Metadata = { title: "Dashboard", robots: { index: false } };

// The app reads the URL and session in the browser, so it streams in behind a boundary;
// only this loading shell is prerendered.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center text-sm text-muted" aria-live="polite">
          Loading your workspace…
        </div>
      }
    >
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
