import Link from "next/link";
import { LogoMark } from "@/components/Logo";
import { SITE } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="container-page grid gap-10 py-12 sm:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5 font-semibold">
            <LogoMark className="size-6" />
            {SITE.name}
          </div>
          <p className="mt-3 max-w-xs text-sm text-muted">{SITE.tagline}.</p>
        </div>
        <FooterCol title="Product" links={[["/#product", "Features"], ["/pricing", "Pricing"], ["/#sources", "Sources"]]} />
        <FooterCol title="Developers" links={[["/docs", "Quickstart"], ["/api-reference", "API reference"]]} />
        <FooterCol title="Company" links={[["/#responsible", "Data policy"], ["/signup", "Create account"]]} />
      </div>
      <div className="container-page flex flex-wrap justify-between gap-2 border-t border-border py-5 text-[13px] text-muted">
        <span>
          © <CopyrightYear /> {SITE.name}
        </span>
        <span>Made in India</span>
      </div>
    </footer>
  );
}

// Cached at build time; Cache Components forbids reading the clock while prerendering.
async function CopyrightYear() {
  "use cache";
  return <>{new Date().getFullYear()}</>;
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <div className="eyebrow">{title}</div>
      <ul className="mt-3 space-y-2 text-sm">
        {links.map(([href, label]) => (
          <li key={href}>
            <Link href={href} className="text-fg-2 hover:text-fg">
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
