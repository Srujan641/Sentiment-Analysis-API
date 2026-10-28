import Link from "next/link";
import { Logo } from "@/components/Logo";

const NAV = [
  { href: "/#product", label: "Product" },
  { href: "/#how", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/90 backdrop-blur">
      <div className="container-page flex h-16 items-center gap-8">
        <Logo />
        <nav className="hidden items-center gap-6 text-sm text-muted md:flex" aria-label="Main">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="hover:text-fg">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Link href="/login" className="btn btn-sm text-fg-2 hover:text-fg">
            Log in
          </Link>
          <Link href="/signup" className="btn btn-primary btn-sm">
            Start free
          </Link>
        </div>
      </div>
    </header>
  );
}
