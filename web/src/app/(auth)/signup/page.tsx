"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/forms/Field";
import { api, ApiError } from "@/lib/api";

type AccountType = "individual" | "organization";

export default function SignupPage() {
  const router = useRouter();
  const [type, setType] = useState<AccountType>("organization");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/signup", {
        method: "POST",
        json: {
          name: f.get("name"),
          email: f.get("email"),
          password: f.get("password"),
          account_type: type,
          organization_name: type === "organization" ? f.get("organization_name") : null,
        },
      });
      router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
      <p className="mt-1.5 text-sm text-muted">Free plan. No card required.</p>
      <form onSubmit={onSubmit} className="card mt-6 space-y-4 p-6">
        <fieldset>
          <legend className="label">Account type</legend>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["organization", "Brand or company", "Your own products"],
                ["individual", "Individual", "Research a product"],
              ] as const
            ).map(([value, title, sub]) => (
              <label
                key={value}
                className={`cursor-pointer rounded-lg border p-3 text-sm transition-colors ${
                  type === value ? "border-fg bg-surface-2" : "border-border-strong hover:bg-surface-2"
                }`}
              >
                <input
                  type="radio"
                  name="account_type"
                  value={value}
                  checked={type === value}
                  onChange={() => setType(value)}
                  className="sr-only"
                />
                <span className="block font-medium">{title}</span>
                <span className="block text-xs text-muted">{sub}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <Field id="name" name="name" label="Your name" autoComplete="name" required maxLength={120} />
        {type === "organization" && (
          <Field id="organization_name" name="organization_name" label="Company name" autoComplete="organization" required maxLength={120} />
        )}
        <Field id="email" name="email" type="email" label="Work email" autoComplete="email" required />
        <Field
          id="password"
          name="password"
          type="password"
          label="Password"
          autoComplete="new-password"
          minLength={10}
          required
          hint="At least 10 characters."
        />
        <FormError message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-fg underline-offset-4 hover:underline">
          Log in
        </Link>
      </p>
    </>
  );
}
