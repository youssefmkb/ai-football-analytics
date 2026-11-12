"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, SubmitButton } from "@/components/form";
import {
  ApiError,
  isStaff,
  type MatchDetail,
  type SquadPlayer,
} from "@/lib/api";
import { formatKickoff, formatScore } from "@/lib/format";
import { errorMessage } from "@/lib/messages";

type Presence = "absent" | "starter" | "substitute";

const PRESENCE_LABELS: Record<Presence, string> = {
  absent: "Absent",
  starter: "Titulaire",
  substitute: "Remplaçant",
};

function presenceOf(match: MatchDetail, playerId: string): Presence {
  const entry = match.lineup.find((e) => e.player_id === playerId);
  if (!entry) return "absent";
  return entry.is_starter ? "starter" : "substitute";
}

export function MatchView() {
  const { id } = useParams<{ id: string }>();
  const { status, me, api } = useAuth();
  const router = useRouter();
  const staff = isStaff(me?.membership?.role);

  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [squad, setSquad] = useState<SquadPlayer[]>([]);
  const [presence, setPresence] = useState<Record<string, Presence>>({});
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scorePending, setScorePending] = useState(false);
  const [scoreError, setScoreError] = useState<string | null>(null);
  const [lineupPending, setLineupPending] = useState(false);
  const [lineupError, setLineupError] = useState<string | null>(null);
  const [lineupSaved, setLineupSaved] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    api<MatchDetail>(`/matches/${id}`)
      .then(async (loaded) => {
        const players = await api<SquadPlayer[]>(`/teams/${loaded.team_id}/players`);
        if (cancelled) return;
        setMatch(loaded);
        setSquad(players);
        setPresence(
          Object.fromEntries(players.map((p) => [p.id, presenceOf(loaded, p.id)])),
        );
      })
      .catch((failure) => {
        if (cancelled) return;
        if (failure instanceof ApiError && [404, 422].includes(failure.status)) {
          setNotFound(true);
        } else {
          setLoadError(errorMessage(failure));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status, api, id]);

  async function onScore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const team = String(form.get("score_team") ?? "");
    const opponent = String(form.get("score_opponent") ?? "");
    if ((team === "") !== (opponent === "")) {
      setScoreError("Saisissez les deux scores, ou laissez les deux champs vides.");
      return;
    }
    setScorePending(true);
    setScoreError(null);
    try {
      setMatch(
        await api<MatchDetail>(`/matches/${id}`, {
          method: "PATCH",
          body: {
            score_team: team === "" ? null : Number(team),
            score_opponent: opponent === "" ? null : Number(opponent),
          },
        }),
      );
    } catch (failure) {
      setScoreError(errorMessage(failure));
    } finally {
      setScorePending(false);
    }
  }

  async function onLineup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!match) return;
    const players = Object.entries(presence)
      .filter(([, value]) => value !== "absent")
      .map(([player_id, value]) => ({ player_id, is_starter: value === "starter" }));
    const starters = players.filter((p) => p.is_starter).length;
    if (starters > match.format) {
      setLineupError(
        `Au football à ${match.format}, il y a ${match.format} titulaires au maximum. Vous en avez sélectionné ${starters}.`,
      );
      return;
    }
    setLineupPending(true);
    setLineupError(null);
    setLineupSaved(false);
    try {
      setMatch(
        await api<MatchDetail>(`/matches/${id}/lineup`, {
          method: "PUT",
          body: { players },
        }),
      );
      setLineupSaved(true);
    } catch (failure) {
      setLineupError(errorMessage(failure));
    } finally {
      setLineupPending(false);
    }
  }

  async function onDelete() {
    if (!match) return;
    try {
      await api(`/matches/${id}`, { method: "DELETE" });
      router.replace(`/teams/${match.team_id}`);
    } catch (failure) {
      setLoadError(errorMessage(failure));
    }
  }

  if (notFound) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">Match introuvable</h1>
        <Link href="/dashboard" className="underline">
          Retour au tableau de bord
        </Link>
      </main>
    );
  }

  if (!match) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-8">
        <FormError message={loadError} />
        {loadError ? null : <p className="text-zinc-500">Chargement</p>}
      </main>
    );
  }

  const starters = Object.values(presence).filter((v) => v === "starter").length;
  const substitutes = Object.values(presence).filter((v) => v === "substitute").length;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 p-8">
      <header>
        <Link href={`/teams/${match.team_id}`} className="text-sm text-zinc-500 underline">
          {match.team_name}
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {match.team_name} contre {match.opponent_name}
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {formatKickoff(match.kickoff_at)} · Football à {match.format}
          {match.location ? ` · ${match.location}` : ""}
        </p>
        <p className="mt-3 text-3xl font-semibold tabular-nums">
          {formatScore(match.score_team, match.score_opponent)}
        </p>
      </header>
      <FormError message={loadError} />

      {staff ? (
        <form onSubmit={onScore} className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Score final</h2>
          <div className="flex items-end gap-3">
            <div className="w-28">
              <Field
                label={match.team_name}
                name="score_team"
                type="number"
                min={0}
                max={99}
                defaultValue={match.score_team ?? ""}
              />
            </div>
            <div className="w-28">
              <Field
                label={match.opponent_name}
                name="score_opponent"
                type="number"
                min={0}
                max={99}
                defaultValue={match.score_opponent ?? ""}
              />
            </div>
            <SubmitButton pending={scorePending}>Enregistrer le score</SubmitButton>
          </div>
          <FormError message={scoreError} />
        </form>
      ) : null}

      <form onSubmit={onLineup} className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">
          Composition ({starters} {starters > 1 ? "titulaires" : "titulaire"},{" "}
          {substitutes} {substitutes > 1 ? "remplaçants" : "remplaçant"})
        </h2>
        {squad.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            L&apos;équipe n&apos;a pas encore de joueurs. Ajoutez-les depuis la page
            de l&apos;équipe.
          </p>
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
            {squad.map((player) => {
              const name = `${player.first_name} ${player.last_name}`;
              return (
                <li key={player.id} className="flex items-center justify-between gap-4 py-2">
                  <span>
                    <span className="inline-block w-8 tabular-nums text-zinc-500">
                      {player.shirt_number ?? ""}
                    </span>
                    <span className="font-medium">{name}</span>
                  </span>
                  {staff ? (
                    <select
                      aria-label={`Présence de ${name}`}
                      value={presence[player.id] ?? "absent"}
                      onChange={(event) => {
                        setLineupSaved(false);
                        setPresence({
                          ...presence,
                          [player.id]: event.target.value as Presence,
                        });
                      }}
                      className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                    >
                      {Object.entries(PRESENCE_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-sm">
                      {PRESENCE_LABELS[presence[player.id] ?? "absent"]}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <FormError message={lineupError} />
        {staff && squad.length > 0 ? (
          <div className="flex items-center gap-3">
            <SubmitButton pending={lineupPending}>Enregistrer la composition</SubmitButton>
            {lineupSaved ? (
              <span role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
                Composition enregistrée.
              </span>
            ) : null}
          </div>
        ) : null}
      </form>

      {staff ? (
        <section className="flex items-center gap-4 border-t border-zinc-200 pt-6 text-sm dark:border-zinc-800">
          {confirmingDelete ? (
            <>
              <span>Supprimer ce match et sa composition ?</span>
              <button
                type="button"
                onClick={onDelete}
                className="font-medium text-red-700 underline dark:text-red-400"
              >
                Confirmer la suppression
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="underline"
              >
                Annuler
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="text-red-700 underline dark:text-red-400"
            >
              Supprimer ce match
            </button>
          )}
        </section>
      ) : null}
    </main>
  );
}
