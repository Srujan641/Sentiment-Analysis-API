import { Poppins } from "next/font/google";
import { SiteFooter } from "@/components/SiteFooter";

const poppins = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

// The home page brings its own header inside the orbit hero.
export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${poppins.variable} flex flex-1 flex-col`}>
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
