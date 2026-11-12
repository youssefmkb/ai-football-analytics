"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, SubmitButton } from "@/components/form";
import { errorMessage } from "@/lib/messages";

export default function RegisterPage() {
  const { status, register } = useAuth();
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await register(
        String(form.get("full_name")),
        String(form.get("email")),
        String(form.get("password")),
      );
    } catch (failure) {
      setError(
        errorMessage(failure, {
          409: "Un compte existe déjà avec cet email.",
        }),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center p-8">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Créer un compte</h1>
        <Field label="Nom complet" name="full_name" autoComplete="name" maxLength={120} required />
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field
          label="Mot de passe"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={10}
          maxLength={128}
          hint="10 caractères au minimum."
          required
        />
        <FormError message={error} />
        <SubmitButton pending={pending}>Créer mon compte</SubmitButton>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Déjà inscrit ?{" "}
          <Link href="/login" className="font-medium underline">
            Se connecter
          </Link>
        </p>
      </form>
    </main>
  );
}
