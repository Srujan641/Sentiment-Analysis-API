export function Field({
  label,
  hint,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <div>
      <label htmlFor={props.id} className="label">
        {label}
      </label>
      <input className="input" {...props} />
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="rounded-lg border border-neg-border bg-neg-bg px-3 py-2.5 text-sm text-neg">
      {message}
    </div>
  );
}
