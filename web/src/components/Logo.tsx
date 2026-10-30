import Link from "next/link";
import { SITE } from "@/lib/site";

export function LogoMark({ className = "size-7" }: { className?: string }) {
  // A pulse line inside a rounded square: reviews as a signal over time.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-accent" />
      <path
        d="M6 17h5l2.5-6 4 11 3-8 1.5 3H26"
        fill="none"
        className="stroke-accent-fg"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2.5 font-semibold tracking-tight text-fg">
      <LogoMark />
      <span>{SITE.name}</span>
    </Link>
  );
}
