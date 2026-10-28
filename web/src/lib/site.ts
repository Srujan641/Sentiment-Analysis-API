// Single place for brand copy and plan data (mirrors app/platform/plans.py).
export const SITE = {
  name: "ReviewPulse",
  tagline: "Know what to fix next, and prove the fix worked",
  description:
    "ReviewPulse turns reviews from your store, app stores, YouTube and Reddit into a ranked fix list, early warnings, and statistical proof that your product changes worked.",
};

export type PlanCard = {
  id: string;
  name: string;
  price: string;
  period: string;
  blurb: string;
  features: string[];
  cta: string;
  highlight?: boolean;
};

export const PLANS: PlanCard[] = [
  {
    id: "free",
    name: "Free",
    price: "₹0",
    period: "forever",
    blurb: "For individuals checking what a product is lacking.",
    features: ["1 product", "3 quick reports / month", "2,000 reviews / month", "Public sources", "30 API requests / min"],
    cta: "Start free",
  },
  {
    id: "starter",
    name: "Starter",
    price: "₹2,999",
    period: "per month",
    blurb: "For brands that want a weekly fix list.",
    features: [
      "5 products",
      "50 reports / month",
      "25,000 reviews / month",
      "Review uploads and push API",
      "Fix verification",
      "Early warning",
      "Weekly refresh",
      "120 API requests / min",
    ],
    cta: "Start with Starter",
    highlight: true,
  },
  {
    id: "growth",
    name: "Growth",
    price: "₹9,999",
    period: "per month",
    blurb: "For brands across many SKUs and channels.",
    features: [
      "25 products",
      "300 reports / month",
      "200,000 reviews / month",
      "Everything in Starter",
      "Webhooks",
      "Daily refresh",
      "Amazon seller connector (coming)",
      "300 API requests / min",
    ],
    cta: "Start with Growth",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "",
    blurb: "For large catalogues and custom integrations.",
    features: ["Unlimited products and reviews", "Custom connectors", "SLA and priority support", "Custom rate limits"],
    cta: "Contact us",
  },
];
