import type { ComponentProps, ReactNode } from "react";

export function Field({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & ComponentProps<"input">) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium">
      {label}
      <input
        {...input}
        className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-base font-normal outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/30 dark:border-zinc-700"
      />
      {hint ? (
        <span className="text-xs font-normal text-zinc-500">{hint}</span>
      ) : null}
    </label>
  );
}

export function SubmitButton({
  pending,
  children,
}: {
  pending: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
    >
      {pending ? "Un instant" : children}
    </button>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
      {message}
    </p>
  );
}
