"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, SubmitButton } from "@/components/form";
import type { Role } from "@/lib/api";
import { errorMessage } from "@/lib/messages";

const ROLE_LABELS: Record<Role, string> = {
  club_admin: "Administrateur du club",
  coach: "Entraîneur",
  player: "Joueur",
};

function CreateClubForm() {
  const { createClub } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      await createClub(String(form.get("name")));
    } catch (failure) {
      setError(
        errorMessage(failure, { 409: "Vous appartenez déjà à un club." }),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <h2 className="text-xl font-semibold">Créer votre club</h2>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Le club est votre espace de travail. Vos équipes, vos matchs et vos
        vidéos y seront rattachés.
      </p>
      <Field label="Nom du club" name="name" maxLength={120} required />
      <FormError message={error} />
      <SubmitButton pending={pending}>Créer le club</SubmitButton>
    </form>
  );
}

export default function DashboardPage() {
  const { status, me, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated" || !me) {
    return (
      <main className="flex flex-1 items-center justify-center p-8 text-zinc-500">
        Chargement
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-10 p-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Bonjour {me.user.full_name}
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {me.user.email}
          </p>
        </div>
        <button
          type="button"
          onClick={() => logout()}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Se déconnecter
        </button>
      </header>

      {me.membership ? (
        <section className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
          <p className="text-sm text-zinc-500">Votre club</p>
          <p className="text-xl font-semibold">
            {me.membership.organization_name}
          </p>
          <p className="mt-1 text-sm">{ROLE_LABELS[me.membership.role]}</p>
        </section>
      ) : (
        <CreateClubForm />
      )}
    </main>
  );
}
