"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, Select, SubmitButton } from "@/components/form";
import { isStaff, type Team } from "@/lib/api";
import { errorMessage } from "@/lib/messages";

export function TeamsSection() {
  const { api, me } = useAuth();
  const staff = isStaff(me?.membership?.role);
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTeams = useCallback(() => api<Team[]>("/teams"), [api]);

  useEffect(() => {
    let cancelled = false;
    fetchTeams()
      .then((loaded) => {
        if (!cancelled) setTeams(loaded);
      })
      .catch((failure) => {
        if (!cancelled) setLoadError(errorMessage(failure));
      });
    return () => {
      cancelled = true;
    };
  }, [fetchTeams]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setPending(true);
    setError(null);
    try {
      await api("/teams", {
        method: "POST",
        body: {
          name: String(form.get("name")),
          default_format: Number(form.get("default_format")),
        },
      });
      formElement.reset();
      setTeams(await fetchTeams());
    } catch (failure) {
      setError(
        errorMessage(failure, {
          409: "Une équipe porte déjà ce nom dans votre club.",
          403: "Seuls les entraîneurs et les administrateurs peuvent créer une équipe.",
        }),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">Équipes</h2>
      <FormError message={loadError} />
      {teams === null && !loadError ? (
        <p className="text-sm text-zinc-500">Chargement</p>
      ) : null}
      {teams?.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Aucune équipe pour l&apos;instant.
        </p>
      ) : null}
      {teams && teams.length > 0 ? (
        <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {teams.map((team) => (
            <li key={team.id}>
              <Link
                href={`/teams/${team.id}`}
                className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
              >
                <span className="font-medium">{team.name}</span>
                <span className="text-sm text-zinc-500">
                  Football à {team.default_format} · {team.player_count}{" "}
                  {team.player_count > 1 ? "joueurs" : "joueur"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {staff ? (
        <form
          onSubmit={onSubmit}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="flex-1">
            <Field label="Nom de l'équipe" name="name" maxLength={120} required />
          </div>
          <Select label="Format" name="default_format" defaultValue="7">
            <option value="5">Football à 5</option>
            <option value="7">Football à 7</option>
            <option value="8">Football à 8</option>
            <option value="11">Football à 11</option>
          </Select>
          <SubmitButton pending={pending}>Ajouter l&apos;équipe</SubmitButton>
        </form>
      ) : null}
      <FormError message={error} />
    </section>
  );
}
