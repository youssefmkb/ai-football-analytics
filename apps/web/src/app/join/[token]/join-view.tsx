"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { FormError } from "@/components/form";
import { ApiError, request, type Role } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/roles";
import { errorMessage } from "@/lib/messages";

type Preview = { organization_name: string; role: Role; expires_at: string };

const BUTTON =
  "rounded-md bg-emerald-700 px-4 py-2 text-center font-medium text-white hover:bg-emerald-800 disabled:opacity-60";
const SECONDARY =
  "rounded-md border border-zinc-300 px-4 py-2 text-center font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900";

export function JoinView() {
  const { token } = useParams<{ token: string }>();
  const { status, me, api, reloadMe } = useAuth();
  const router = useRouter();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [joined, setJoined] = useState(false);

  useEffect(() => {
    let cancelled = false;
    request<Preview>(`/invitations/${encodeURIComponent(token)}`)
      .then((loaded) => {
        if (!cancelled) setPreview(loaded);
      })
      .catch((failure) => {
        if (cancelled) return;
        if (failure instanceof ApiError && failure.status === 404) setInvalid(true);
        else setError(errorMessage(failure));
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onJoin() {
    setPending(true);
    setError(null);
    try {
      await api(`/invitations/${encodeURIComponent(token)}/accept`, { method: "POST" });
      // Set first: once the user is reloaded with their new club, the page
      // would otherwise say they already belong to one.
      setJoined(true);
      await reloadMe();
      router.replace("/dashboard");
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 404) setInvalid(true);
      else
        setError(
          errorMessage(failure, { 409: "Vous appartenez déjà à un club." }),
        );
      setPending(false);
    }
  }

  const next = encodeURIComponent(`/join/${token}`);

  let body;
  if (joined && preview) {
    body = (
      <p role="status" className="text-zinc-600 dark:text-zinc-400">
        Vous avez rejoint {preview.organization_name}. Ouverture du tableau de bord.
      </p>
    );
  } else if (invalid) {
    body = (
      <>
        <h1 className="text-2xl font-semibold tracking-tight">Lien invalide</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Ce lien d&apos;invitation a déjà été utilisé, a expiré ou a été annulé.
          Demandez un nouveau lien à l&apos;administrateur du club.
        </p>
        <Link href="/" className="underline">
          Retour à l&apos;accueil
        </Link>
      </>
    );
  } else if (!preview || status === "loading") {
    body = error ? null : <p className="text-zinc-500">Chargement</p>;
  } else {
    const invitation = (
      <>
        <h1 className="text-2xl font-semibold tracking-tight">
          Rejoindre {preview.organization_name}
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Vous êtes invité en tant que{" "}
          <strong>{ROLE_LABELS[preview.role].toLowerCase()}</strong>.
        </p>
      </>
    );
    if (status === "anonymous") {
      body = (
        <>
          {invitation}
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Créez votre compte ou connectez-vous pour accepter l&apos;invitation.
          </p>
          <div className="flex flex-col gap-3">
            <Link href={`/register?next=${next}`} className={BUTTON}>
              Créer un compte
            </Link>
            <Link href={`/login?next=${next}`} className={SECONDARY}>
              J&apos;ai déjà un compte
            </Link>
          </div>
        </>
      );
    } else if (me?.membership) {
      body = (
        <>
          {invitation}
          <p className="rounded-md bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-900">
            Vous appartenez déjà au club {me.membership.organization_name}. Un
            compte ne peut appartenir qu&apos;à un seul club pour l&apos;instant.
          </p>
          <Link href="/dashboard" className="underline">
            Retour au tableau de bord
          </Link>
        </>
      );
    } else {
      body = (
        <>
          {invitation}
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Connecté en tant que {me?.user.email}.
          </p>
          <button type="button" onClick={onJoin} disabled={pending} className={BUTTON}>
            {pending ? "Un instant" : "Rejoindre le club"}
          </button>
        </>
      );
    }
  }

  return (
    <main className="flex flex-1 flex-col items-center justify-center p-8">
      <div className="flex w-full max-w-sm flex-col gap-4">
        {body}
        <FormError message={error} />
      </div>
    </main>
  );
}
