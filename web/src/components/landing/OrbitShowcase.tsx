"use client";

// Orbit showcase, adapted from the SoundMart prototype (soundmart-frontend.zip): products
// sit on an ellipse and rotate; the front one is spotlit on a coloured oval.
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { LogoMark } from "@/components/Logo";
import { SITE } from "@/lib/site";

type Item = { title: string; cat: string; checks: string; color: string; img: string; w: number; h: number };

// Categories, not specific products: the page shows what ReviewPulse checks, not claims about a brand.
const ITEMS: Item[] = [
  { title: "Headphones", cat: "Over-ear headphones", checks: "Battery · Comfort · Sound · Build", color: "#5fb36a", img: "/products/headphones.png", w: 338, h: 373 },
  { title: "Earbuds", cat: "True wireless", checks: "Fit · Call quality · Case battery · Pairing", color: "#e8667c", img: "/products/earbuds.png", w: 577, h: 611 },
  { title: "Smartphones", cat: "Mobiles", checks: "Heating · Camera · Battery · Updates", color: "#f2b441", img: "/products/phone.png", w: 635, h: 760 },
  { title: "Smartwatches", cat: "Wearables", checks: "Strap comfort · Sensors · Battery · App", color: "#4aa3e0", img: "/products/watch.png", w: 662, h: 760 },
  { title: "Speakers", cat: "Bluetooth speakers", checks: "Loudness · Bass · Battery · Durability", color: "#9b6df0", img: "/products/speaker.png", w: 402, h: 760 },
];
const N = ITEMS.length;
const AUTOPLAY_MS = 4500;

const NAV = [
  { href: "/me", label: "Research" },
  { href: "/#product", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  { href: "/business/login", label: "Business" },
];

export function OrbitShowcase() {
  const [active, setActive] = useState(0);
  const [size, setSize] = useState({ w: 1200, h: 520 });
  const [shown, setShown] = useState(0); // info text lags slightly so it can fade
  const [swapping, setSwapping] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const paused = useRef(false);
  const startX = useRef<number | null>(null);

  const goTo = useCallback((i: number) => setActive(((i % N) + N) % N), []);
  const next = useCallback(() => setActive((a) => (a + 1) % N), []);
  const prev = useCallback(() => setActive((a) => (a - 1 + N) % N), []);

  const restart = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    timer.current = setInterval(() => {
      if (!paused.current) next();
    }, AUTOPLAY_MS);
  }, [next]);

  useEffect(() => {
    restart();
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [restart]);

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
    };
    addEventListener("keydown", onKey);
    return () => {
      ro.disconnect();
      removeEventListener("keydown", onKey);
    };
  }, [next, prev]);

  // Fade the caption out, swap it, fade it in.
  useEffect(() => {
    if (active === shown) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- drives a short fade transition
    setSwapping(true);
    const t = setTimeout(() => {
      setShown(active);
      setSwapping(false);
    }, 220);
    return () => clearTimeout(t);
  }, [active, shown]);

  const small = size.w < 900;
  const Rx = Math.min(size.w * 0.34, 470);
  const Ry = Math.min(size.h * 0.22, 110);

  function style(i: number): React.CSSProperties {
    let d = i - active; // shortest signed distance around the ring
    if (d > N / 2) d -= N;
    if (d < -N / 2) d += N;
    const th = d * ((2 * Math.PI) / N);
    const x = Math.sin(th) * Rx;
    const y = -(1 - Math.cos(th)) * Ry; // back items rise, the front one sits low
    const depth = (Math.cos(th) + 1) / 2; // 1 front … 0 back
    const s = (small ? 0.55 : 0.62) + depth * (small ? 0.45 : 0.5);
    const isActive = i === active;
    return {
      transform: `translate(-50%,-50%) translate(${x}px,${y}px) scale(${isActive ? s * 1.08 : s})`,
      zIndex: Math.round(depth * 100),
      opacity: 0.4 + depth * 0.6,
      filter: isActive ? "none" : `blur(${((1 - depth) * 2.2).toFixed(1)}px) brightness(${(0.8 + depth * 0.2).toFixed(2)})`,
      ["--c" as string]: ITEMS[i].color,
    };
  }

  const item = ITEMS[shown];

  return (
    <section className="orbit relative overflow-hidden text-white" aria-label="Products ReviewPulse can research">
      <div className="orbit-rings" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>

      <header className="relative z-20 mx-auto flex max-w-[1240px] items-center justify-between px-4 py-5 sm:px-7 sm:py-6">
        <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold tracking-tight sm:text-[22px]">
          <LogoMark className="size-8" />
          {SITE.name}
        </Link>
        <nav className="hidden md:block" aria-label="Main">
          <ul className="flex gap-8">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link href={n.href} className="text-[12.5px] font-medium uppercase tracking-[0.08em] text-white/90 hover:text-[#f4883a]">
                  {n.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-[12.5px] font-medium uppercase tracking-[0.08em] text-white/90 hover:text-[#f4883a]">
            Log in
          </Link>
          <Link href="/signup" className="rounded-full bg-[#f4883a] px-4 py-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-white hover:bg-[#ff9a52]">
            Start free
          </Link>
        </div>
      </header>

      <div
        ref={stageRef}
        className="orbit-stage relative z-10 w-full"
        aria-roledescription="carousel"
        onMouseEnter={() => (paused.current = true)}
        onMouseLeave={() => (paused.current = false)}
        onPointerDown={(e) => (startX.current = e.clientX)}
        onPointerUp={(e) => {
          if (startX.current === null) return;
          const dx = e.clientX - startX.current;
          startX.current = null;
          if (Math.abs(dx) > 60) {
            if (dx < 0) next();
            else prev();
            restart();
          }
        }}
      >
        {ITEMS.map((it, i) => (
          <div
            key={it.title}
            className={`orbit-item ${i === active ? "is-active" : ""}`}
            style={style(i)}
            onClick={() => {
              goTo(i);
              restart();
            }}
            role="group"
            aria-roledescription="slide"
            aria-label={`${it.title}, ${i + 1} of ${N}`}
            aria-hidden={i !== active}
          >
            <div className="orbit-oval" />
            <div className="orbit-prod">
              <Image src={it.img} alt={it.title} width={it.w} height={it.h} priority={i === 0} draggable={false} sizes="250px" />
            </div>
            <Link
              href="/signup"
              className="orbit-cta"
              aria-label={`Research ${it.title.toLowerCase()}`}
              tabIndex={i === active ? 0 : -1}
              onClick={(e) => e.stopPropagation()}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="m20 20-4.2-4.2" />
              </svg>
            </Link>
          </div>
        ))}
      </div>

      <div className="relative z-30 mx-auto -mt-6 flex w-full max-w-[1180px] justify-between px-4 sm:px-7">
        <button
          className="orbit-pill"
          onClick={() => {
            prev();
            restart();
          }}
        >
          Prev product
        </button>
        <button
          className="orbit-pill"
          onClick={() => {
            next();
            restart();
          }}
        >
          Next product
        </button>
      </div>

      <div className={`orbit-info relative z-10 px-4 pb-14 text-center ${swapping ? "is-swapping" : ""}`} aria-live="polite">
        <div className="text-xs uppercase tracking-[0.25em] text-white/60">{item.cat}</div>
        <h1 className="orbit-title mt-1 text-[26px] font-medium tracking-[0.08em] sm:text-[34px]">{item.title}</h1>
        <div className="orbit-checks mt-1.5 text-[15px] font-semibold text-[#ff8a6b] sm:text-lg">{item.checks}</div>
        <div className="mt-4 flex justify-center gap-2" role="tablist" aria-label="Choose a product">
          {ITEMS.map((it, i) => (
            <button
              key={it.title}
              role="tab"
              aria-selected={i === active}
              aria-label={it.title}
              className={`h-2 rounded-full transition-all ${i === active ? "w-6 bg-[#f4883a]" : "w-2 bg-white/30"}`}
              onClick={() => {
                goTo(i);
                restart();
              }}
            />
          ))}
        </div>
        <p className="mx-auto mt-6 max-w-md text-sm text-white/70 sm:text-base">
          Know what any product is lacking before you buy it, from reviews across the web.
        </p>
        <Link href="/signup" className="mt-5 inline-flex h-11 items-center rounded-full bg-white px-6 text-sm font-semibold text-[#0b1b52] hover:bg-white/90">
          Research a product free
        </Link>
      </div>
    </section>
  );
}
