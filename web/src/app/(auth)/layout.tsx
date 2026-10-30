import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="container-page flex h-16 items-center">
        <Logo />
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pb-16 pt-8 sm:pt-16">
        <div className="w-full max-w-[400px]">{children}</div>
      </main>
      <footer className="pb-8 text-center text-[13px] text-muted">
        <Link href="/" className="hover:text-fg">
          ← Back to home
        </Link>
      </footer>
    </div>
  );
}
