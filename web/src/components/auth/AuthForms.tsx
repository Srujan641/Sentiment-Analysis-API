"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/forms/Field";
import { api, ApiError, type Me } from "@/lib/api";

type Portal = "personal" | "business";

const home = (me: Me) => (me.organization.account_type === "organization" ? "/app" : "/me");

export function LoginForm({ portal }: { portal: Portal }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const other: Portal = portal === "personal" ? "business" : "personal";

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/v1/auth/login", {
        method: "POST",
        json: { email: f.get("email"), password: f.get("password"), portal },
      });
      router.push(home(me));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <>
      <p className="eyebrow">{portal === "business" ? "Business" : "Personal"}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Log in</h1>
      <p className="mt-1.5 text-sm text-muted">
        {portal === "business" ? "Analyse your products' reviews and reports." : "Research any product before you buy."}
      </p>
      <form onSubmit={onSubmit} className="card mt-6 space-y-4 p-6">
        <Field id="email" name="email" type="email" label="Email" autoComplete="email" required />
        <Field id="password" name="password" type="password" label="Password" autoComplete="current-password" required />
        <FormError message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">
        New here?{" "}
        <Link href={portal === "business" ? "/business/signup" : "/signup"} className="font-medium text-fg underline-offset-4 hover:underline">
          Create an account
        </Link>
      </p>
      <p className="mt-2 text-center text-sm text-muted">
        <Link href={other === "business" ? "/business/login" : "/login"} className="underline-offset-4 hover:underline">
          {other === "business" ? "Business login →" : "Personal login →"}
        </Link>
      </p>
    </>
  );
}

export function SignupForm({ portal }: { portal: Portal }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const business = portal === "business";

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/v1/auth/signup", {
        method: "POST",
        json: {
          name: f.get("name"),
          email: f.get("email"),
          password: f.get("password"),
          account_type: business ? "organization" : "individual",
          organization_name: business ? f.get("organization_name") : null,
        },
      });
      router.push(home(me));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <>
      <p className="eyebrow">{business ? "Business" : "Personal"}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1.5 text-sm text-muted">
        {business ? "Free plan for one product. No card required." : "10 product researches a day, free. No card required."}
      </p>
      <form onSubmit={onSubmit} className="card mt-6 space-y-4 p-6">
        <Field id="name" name="name" label="Your name" autoComplete="name" required maxLength={120} />
        {business && <Field id="organization_name" name="organization_name" label="Company name" autoComplete="organization" required maxLength={120} />}
        <Field id="email" name="email" type="email" label={business ? "Work email" : "Email"} autoComplete="email" required />
        <Field id="password" name="password" type="password" label="Password" autoComplete="new-password" minLength={10} required hint="At least 10 characters." />
        <FormError message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href={business ? "/business/login" : "/login"} className="font-medium text-fg underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
      <p className="mt-2 text-center text-sm text-muted">
        <Link href={business ? "/signup" : "/business/signup"} className="underline-offset-4 hover:underline">
          {business ? "Just researching products? Personal sign-up →" : "Selling products? Business sign-up →"}
        </Link>
      </p>
    </>
  );
}
