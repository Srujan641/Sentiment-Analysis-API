import type { Metadata } from "next";
import { Suspense } from "react";
import { PersonalShell } from "@/components/personal/PersonalShell";

export const metadata: Metadata = { title: "Research", robots: { index: false } };

export default function PersonalLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="flex flex-1 items-center justify-center text-sm text-muted">Loading…</div>}>
      <PersonalShell>{children}</PersonalShell>
    </Suspense>
  );
}
