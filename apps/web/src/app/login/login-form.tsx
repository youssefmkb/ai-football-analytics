"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, SubmitButton } from "@/components/form";
import { errorMessage } from "@/lib/messages";
import { safeNextPath } from "@/lib/next-path";

export function LoginForm() {
  const { status, login } = useAuth();
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await login(String(form.get("email")), String(form.get("password")));
    } catch (failure) {
      setError(
        errorMessage(failure, { 401: "Email ou mot de passe incorrect." }),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center p-8">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Connexion</h1>
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field
          label="Mot de passe"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <FormError message={error} />
        <SubmitButton pending={pending}>Se connecter</SubmitButton>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Pas encore de compte ?{" "}
          <Link href={next === "/dashboard" ? "/register" : `/register?next=${encodeURIComponent(next)}`} className="font-medium underline">
            Créer un compte
          </Link>
        </p>
      </form>
    </main>
  );
}
