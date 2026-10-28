"use client";

import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

// three.js only runs in the browser; the rest of the page stays prerendered.
const StoryScene = dynamic(() => import("./three/StoryScene"), { ssr: false });

const STEPS = 5;

/** Scroll ranges must sit inside 0..1 and strictly increase, or the browser's
 *  accelerated scroll animations reject them. */
function range(points: number[]): number[] {
  const out = points.map((x) => Math.min(1, Math.max(0, x)));
  for (let i = 1; i < out.length; i++) if (out[i] <= out[i - 1]) out[i] = out[i - 1] + 1e-4;
  const over = out[out.length - 1] - 1;
  return over > 0 ? out.map((x) => x - over) : out;
}

type Chip = { label: string; tone: "neg" | "pos"; value: string };
type Panel = { eyebrow: string; title: string; body: string; chips?: Chip[] };

const PANELS: Panel[] = [
  {
    eyebrow: "Review intelligence",
    title: "Every review. Every product. One clear fix list.",
    body: "Headphones, phones, laptops, clothes. ReviewPulse reads what customers say about any product and tells you what to fix first, then proves whether the fix worked.",
  },
  {
    eyebrow: "Headphones",
    title: "Battery life is costing you 0.31★",
    body: "Clause-level analysis separates “great sound” from “battery dies in two hours” in the same review.",
    chips: [
      { label: "Battery life", tone: "neg", value: "−0.31★" },
      { label: "Ear cushions peeling", tone: "neg", value: "−0.12★" },
      { label: "Sound quality", tone: "pos", value: "1,204 praise" },
    ],
  },
  {
    eyebrow: "Smartphones",
    title: "Heating started three weeks ago",
    body: "Early warning compares each issue with its own baseline and flags a rise before it reaches your rating.",
    chips: [
      { label: "Heats up while gaming", tone: "neg", value: "2% → 9%" },
      { label: "Camera in low light", tone: "neg", value: "−0.08★" },
      { label: "Display brightness", tone: "pos", value: "880 praise" },
    ],
  },
  {
    eyebrow: "Laptops",
    title: "The new fan cut noise complaints by 41%",
    body: "Log the change you shipped. A statistical test, adjusted for trend, tells you whether complaints really fell.",
    chips: [
      { label: "Fan noise", tone: "pos", value: "−41%, p = 0.004" },
      { label: "Keyboard flex", tone: "neg", value: "−0.06★" },
      { label: "Battery backup", tone: "pos", value: "640 praise" },
    ],
  },
  {
    eyebrow: "Clothing",
    title: "“Size runs small” is your #1 return reason",
    body: "Specific issues are discovered from the reviews themselves, not just matched against a fixed list.",
    chips: [
      { label: "Size runs small", tone: "neg", value: "−0.22★" },
      { label: "Colour fades after wash", tone: "neg", value: "−0.09★" },
      { label: "Fabric feel", tone: "pos", value: "2,310 praise" },
    ],
  },
  {
    eyebrow: "One engine",
    title: "From scattered reviews to the next decision.",
    body: "Upload your exports, connect app stores and the web, and get your first report in minutes.",
  },
];

export function ScrollStory() {
  const reduce = useReducedMotion();
  const [webgl, setWebgl] = useState<boolean | null>(null);

  useEffect(() => {
    const c = document.createElement("canvas");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time capability check
    setWebgl(Boolean(c.getContext("webgl2") || c.getContext("webgl")));
  }, []);

  if (reduce || webgl === false) return <StaticStory />;
  return <AnimatedStory />;
}

function AnimatedStory() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [compact, setCompact] = useState(false);
  const [active, setActive] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const update = () => setCompact(mq.matches);
    update();
    mq.addEventListener("change", update);
    const io = new IntersectionObserver(([e]) => setActive(e.isIntersecting), { rootMargin: "200px" });
    if (ref.current) io.observe(ref.current);
    return () => {
      mq.removeEventListener("change", update);
      io.disconnect();
    };
  }, []);

  return (
    <section ref={ref} className="relative bg-[#0b0b0d] text-[#ededef]" style={{ height: `${(STEPS + 1) * 100}vh` }}>
      <div className="sticky top-0 h-screen overflow-hidden">
        <div className="absolute inset-0">
          <StoryScene progress={scrollYProgress} compact={compact} active={active} />
        </div>
        <div className="container-page pointer-events-none relative h-full">
          {PANELS.map((p, i) => (
            <PanelView key={p.eyebrow} panel={p} index={i} progress={scrollYProgress} />
          ))}
        </div>
        <ProgressDots progress={scrollYProgress} />
        <ScrollHint progress={scrollYProgress} />
      </div>
    </section>
  );
}

function PanelView({ panel, index, progress }: { panel: Panel; index: number; progress: MotionValue<number> }) {
  const at = index / STEPS;
  const w = 0.55 / STEPS;
  // First panel is visible from the top; last stays visible at the end.
  const input = index === 0 ? [0, at + w * 0.5, at + w] : index === STEPS ? [at - w, at - w * 0.5, 1] : [at - w, at, at + w];
  const output = index === 0 ? [1, 1, 0] : index === STEPS ? [0, 1, 1] : [0, 1, 0];
  const r = range(input);
  const opacity = useTransform(progress, r, output);
  const y = useTransform(progress, r, index === 0 ? [0, 0, -40] : index === STEPS ? [40, 0, 0] : [40, 0, -40]);
  const hero = index === 0;

  return (
    <motion.div
      style={{ opacity, y }}
      className="absolute inset-x-4 bottom-6 sm:inset-x-6 md:bottom-auto md:left-6 md:top-1/2 md:max-w-[480px] md:-translate-y-1/2"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#9a9aa3]">{panel.eyebrow}</p>
      <h2
        className={`mt-3 font-semibold tracking-[-0.03em] text-balance ${
          hero ? "text-[34px] leading-[1.05] sm:text-[56px]" : "text-[28px] leading-[1.1] sm:text-[42px]"
        }`}
      >
        {panel.title}
      </h2>
      <p className="mt-4 max-w-md text-[15px] leading-relaxed text-[#b4b4bc] sm:text-lg">{panel.body}</p>
      {panel.chips && (
        <ul className="mt-6 space-y-2">
          {panel.chips.map((c) => (
            <li
              key={c.label}
              className="flex max-w-sm items-center justify-between gap-4 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm backdrop-blur"
            >
              <span className="flex items-center gap-2.5">
                <span className={`size-2 rounded-full ${c.tone === "neg" ? "bg-[#f87171]" : "bg-[#4ade80]"}`} aria-hidden="true" />
                {c.label}
              </span>
              <span className={`tabular-nums ${c.tone === "neg" ? "text-[#f87171]" : "text-[#4ade80]"}`}>{c.value}</span>
            </li>
          ))}
          <li className="pt-1 text-xs text-[#77777f]">Example insights</li>
        </ul>
      )}
      {(hero || index === STEPS) && (
        <div className="pointer-events-auto mt-8 flex flex-wrap gap-3">
          <Link href="/signup" className="btn h-11 bg-white px-5 text-[#0b0b0d] hover:bg-white/90">
            Start free
          </Link>
          <Link href="/docs" className="btn h-11 border border-white/20 px-5 text-white hover:bg-white/10">
            Read the API docs
          </Link>
        </div>
      )}
    </motion.div>
  );
}

function ProgressDots({ progress }: { progress: MotionValue<number> }) {
  return (
    <div className="absolute right-4 top-1/2 hidden -translate-y-1/2 flex-col gap-2.5 md:flex" aria-hidden="true">
      {PANELS.map((_, i) => (
        <Dot key={i} index={i} progress={progress} />
      ))}
    </div>
  );
}

function Dot({ index, progress }: { index: number; progress: MotionValue<number> }) {
  const at = index / STEPS;
  const w = 0.5 / STEPS;
  const r = range([at - w, at, at + w]);
  const scale = useTransform(progress, r, [1, 1.8, 1]);
  const opacity = useTransform(progress, r, [0.35, 1, 0.35]);
  return <motion.span style={{ scale, opacity }} className="block size-1.5 rounded-full bg-white" />;
}

function ScrollHint({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, range([0, 0.04]), [1, 0]);
  return (
    <motion.div style={{ opacity }} className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 text-xs text-[#77777f] md:block">
      Scroll to explore
    </motion.div>
  );
}

/* Reduced motion or no WebGL: the same story as plain sections. */
function StaticStory() {
  return (
    <section className="bg-[#0b0b0d] text-[#ededef]">
      <div className="container-page space-y-16 py-20">
        {PANELS.map((p, i) => (
          <div key={p.eyebrow} className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#9a9aa3]">{p.eyebrow}</p>
            <h2 className={`mt-3 font-semibold tracking-[-0.03em] ${i === 0 ? "text-[40px] leading-tight" : "text-[30px]"}`}>{p.title}</h2>
            <p className="mt-3 text-[#b4b4bc]">{p.body}</p>
            {p.chips && (
              <ul className="mt-4 flex flex-wrap gap-2 text-sm">
                {p.chips.map((c) => (
                  <li key={c.label} className="rounded-md border border-white/10 px-2.5 py-1">
                    {c.label} <span className={c.tone === "neg" ? "text-[#f87171]" : "text-[#4ade80]"}>{c.value}</span>
                  </li>
                ))}
              </ul>
            )}
            {i === 0 && (
              <div className="mt-6 flex gap-3">
                <Link href="/signup" className="btn h-11 bg-white px-5 text-[#0b0b0d]">
                  Start free
                </Link>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
