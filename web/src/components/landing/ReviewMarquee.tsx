// A moving wall of example reviews, each tagged the way the engine reads it.
type Item = { cat: string; text: string; aspect: string; tone: "neg" | "pos" };

const ROW_A: Item[] = [
  { cat: "Headphones", text: "Sound is incredible but the battery dies in two hours.", aspect: "battery life", tone: "neg" },
  { cat: "T-shirt", text: "Ordered my usual M and it fits like an S.", aspect: "size and fit", tone: "neg" },
  { cat: "Laptop", text: "Keyboard is a joy to type on, quiet and firm.", aspect: "keyboard", tone: "pos" },
  { cat: "Smartphone", text: "Gets really hot after 20 minutes of gaming.", aspect: "heating", tone: "neg" },
  { cat: "Face wash", text: "Gentle on my skin, no breakouts after a month.", aspect: "skin effect", tone: "pos" },
  { cat: "Sneakers", text: "Sole started peeling within three weeks.", aspect: "durability", tone: "neg" },
];
const ROW_B: Item[] = [
  { cat: "Smartwatch", text: "Strap is comfortable enough to sleep with.", aspect: "comfort", tone: "pos" },
  { cat: "Kurta", text: "Colour faded badly after the first wash.", aspect: "colour fastness", tone: "neg" },
  { cat: "Earbuds", text: "Pairing is instant and the case is tiny.", aspect: "connectivity", tone: "pos" },
  { cat: "Laptop", text: "Fan noise is loud even on simple tasks.", aspect: "fan noise", tone: "neg" },
  { cat: "Smartphone", text: "Night photos look clean and sharp.", aspect: "camera", tone: "pos" },
  { cat: "Backpack", text: "Zip broke on the first trip.", aspect: "build quality", tone: "neg" },
];

function Row({ items, reverse }: { items: Item[]; reverse?: boolean }) {
  return (
    <div className="group flex overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]">
      <ul
        className={`flex w-max shrink-0 gap-3 pr-3 group-hover:[animation-play-state:paused] ${
          reverse ? "animate-[marquee_60s_linear_infinite_reverse]" : "animate-[marquee_55s_linear_infinite]"
        }`}
      >
        {[...items, ...items].map((it, i) => (
          <li key={i} aria-hidden={i >= items.length} className="card w-[300px] shrink-0 p-4">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="font-medium text-muted">{it.cat}</span>
              <span
                className={`rounded-md border px-1.5 py-0.5 font-medium ${
                  it.tone === "neg" ? "border-neg-border bg-neg-bg text-neg" : "border-pos-border bg-pos-bg text-pos"
                }`}
              >
                {it.aspect}
              </span>
            </div>
            <p className="mt-2 text-sm text-fg-2">“{it.text}”</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReviewMarquee() {
  return (
    <section className="border-b border-border py-14" aria-label="Example reviews and the aspects detected">
      <p className="eyebrow container-page mb-6">Reads reviews like a person, at the scale of a machine</p>
      <div className="space-y-3">
        <Row items={ROW_A} />
        <Row items={ROW_B} reverse />
      </div>
      <p className="container-page mt-4 text-xs text-muted">Example reviews.</p>
    </section>
  );
}
