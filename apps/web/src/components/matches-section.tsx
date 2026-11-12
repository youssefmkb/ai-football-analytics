"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, SubmitButton } from "@/components/form";
import { isStaff, type Match } from "@/lib/api";
import { formatKickoff, formatScore } from "@/lib/format";
import { errorMessage } from "@/lib/messages";

export function MatchesSection({ teamId }: { teamId: string }) {
  const { api, me } = useAuth();
  const staff = isStaff(me?.membership?.role);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMatches = useCallback(
    () => api<Match[]>(`/matches?team_id=${teamId}`),
    [api, teamId],
  );

  useEffect(() => {
    let cancelled = false;
    fetchMatches()
      .then((loaded) => {
        if (!cancelled) setMatches(loaded);
      })
      .catch((failure) => {
        if (!cancelled) setLoadError(errorMessage(failure));
      });
    return () => {
      cancelled = true;
    };
  }, [fetchMatches]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setPending(true);
    setError(null);
    try {
      await api("/matches", {
        method: "POST",
        body: {
          team_id: teamId,
          opponent_name: String(form.get("opponent_name")),
          // The field holds local time: toISOString() attaches the offset.
          kickoff_at: new Date(String(form.get("kickoff_at"))).toISOString(),
          location: String(form.get("location") ?? ""),
        },
      });
      formElement.reset();
      setMatches(await fetchMatches());
    } catch (failure) {
      setError(
        errorMessage(failure, {
          403: "Seuls les entraîneurs et les administrateurs peuvent créer un match.",
        }),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">Matchs</h2>
      <FormError message={loadError} />
      {matches?.length === 0 ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Aucun match pour l&apos;instant.
        </p>
      ) : null}
      {matches && matches.length > 0 ? (
        <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {matches.map((match) => (
            <li key={match.id}>
              <Link
                href={`/matches/${match.id}`}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
              >
                <span className="font-medium">contre {match.opponent_name}</span>
                <span className="text-sm text-zinc-500">
                  {formatKickoff(match.kickoff_at)} ·{" "}
                  {formatScore(match.score_team, match.score_opponent)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {staff ? (
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <h3 className="font-semibold">Ajouter un match</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Adversaire" name="opponent_name" maxLength={120} required />
            <Field
              label="Date et heure du coup d'envoi"
              name="kickoff_at"
              type="datetime-local"
              required
            />
            <Field label="Lieu" name="location" maxLength={160} hint="Facultatif." />
          </div>
          <FormError message={error} />
          <div>
            <SubmitButton pending={pending}>Ajouter le match</SubmitButton>
          </div>
        </form>
      ) : null}
    </section>
  );
}
