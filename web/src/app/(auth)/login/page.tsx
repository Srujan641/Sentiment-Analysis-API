"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Field, FormError } from "@/components/forms/Field";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/login", { method: "POST", json: { email: form.get("email"), password: form.get("password") } });
      router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
      <p className="mt-1.5 text-sm text-muted">Welcome back.</p>
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
        <Link href="/signup" className="font-medium text-fg underline-offset-4 hover:underline">
          Create an account
        </Link>
      </p>
    </>
  );
}
