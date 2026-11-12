"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, Select, SubmitButton } from "@/components/form";
import { MatchesSection } from "@/components/matches-section";
import {
  ApiError,
  isStaff,
  type Position,
  type SquadPlayer,
  type Team,
} from "@/lib/api";
import { errorMessage } from "@/lib/messages";

const POSITION_LABELS: Record<Position, string> = {
  goalkeeper: "Gardien",
  defender: "Défenseur",
  midfielder: "Milieu",
  forward: "Attaquant",
};

const WRITE_ERRORS = {
  409: "Ce numéro de maillot est déjà pris dans l'équipe.",
  403: "Seuls les entraîneurs et les administrateurs peuvent modifier l'effectif.",
};

export function TeamView() {
  const { id } = useParams<{ id: string }>();
  const { status, me, api } = useAuth();
  const router = useRouter();
  const staff = isStaff(me?.membership?.role);

  const [team, setTeam] = useState<Team | null>(null);
  const [squad, setSquad] = useState<SquadPlayer[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  const fetchSquad = useCallback(
    () => api<SquadPlayer[]>(`/teams/${id}/players`),
    [api, id],
  );

  useEffect(() => {
    if (status !== "authenticated") return;
    let cancelled = false;
    Promise.all([api<Team>(`/teams/${id}`), fetchSquad()])
      .then(([loadedTeam, loadedSquad]) => {
        if (cancelled) return;
        setTeam(loadedTeam);
        setSquad(loadedSquad);
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
  }, [status, api, id, fetchSquad]);

  async function onAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const number = String(form.get("shirt_number") ?? "");
    const position = String(form.get("position") ?? "");
    setPending(true);
    setError(null);
    try {
      await api(`/teams/${id}/players`, {
        method: "POST",
        body: {
          first_name: String(form.get("first_name")),
          last_name: String(form.get("last_name")),
          shirt_number: number ? Number(number) : null,
          position: position || null,
        },
      });
      formElement.reset();
      setSquad(await fetchSquad());
    } catch (failure) {
      setError(errorMessage(failure, WRITE_ERRORS));
    } finally {
      setPending(false);
    }
  }

  async function onRemove(player: SquadPlayer) {
    setError(null);
    try {
      await api(`/teams/${id}/players/${player.id}`, { method: "DELETE" });
      setSquad(await fetchSquad());
    } catch (failure) {
      setError(
        errorMessage(failure, {
          ...WRITE_ERRORS,
          409: `${player.first_name} ${player.last_name} figure dans la composition d'un match et ne peut pas être retiré.`,
        }),
      );
    }
  }

  if (notFound) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">Équipe introuvable</h1>
        <Link href="/dashboard" className="underline">
          Retour au tableau de bord
        </Link>
      </main>
    );
  }

  if (!team) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-8">
        <FormError message={loadError} />
        {loadError ? null : <p className="text-zinc-500">Chargement</p>}
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 p-8">
      <header>
        <Link href="/dashboard" className="text-sm text-zinc-500 underline">
          Tableau de bord
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{team.name}</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Football à {team.default_format}
        </p>
      </header>

      <MatchesSection teamId={team.id} />

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">Effectif ({squad.length})</h2>
        {squad.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Aucun joueur pour l&apos;instant.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-zinc-500">
              <tr className="border-b border-zinc-200 dark:border-zinc-800">
                <th className="w-12 py-2 font-medium">N°</th>
                <th className="py-2 font-medium">Joueur</th>
                <th className="py-2 font-medium">Poste</th>
                {staff ? <th className="py-2" /> : null}
              </tr>
            </thead>
            <tbody>
              {squad.map((player) => (
                <tr
                  key={player.id}
                  className="border-b border-zinc-100 dark:border-zinc-900"
                >
                  <td className="py-2 tabular-nums">{player.shirt_number ?? ""}</td>
                  <td className="py-2 font-medium">
                    {player.first_name} {player.last_name}
                  </td>
                  <td className="py-2">
                    {player.position ? POSITION_LABELS[player.position] : ""}
                  </td>
                  {staff ? (
                    <td className="py-2 text-right">
                      <button
                        type="button"
                        onClick={() => onRemove(player)}
                        aria-label={`Retirer ${player.first_name} ${player.last_name}`}
                        className="text-red-700 underline dark:text-red-400"
                      >
                        Retirer
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {staff ? (
        <form onSubmit={onAdd} className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Ajouter un joueur</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Prénom" name="first_name" maxLength={80} required />
            <Field label="Nom" name="last_name" maxLength={80} required />
            <Field
              label="Numéro de maillot"
              name="shirt_number"
              type="number"
              min={1}
              max={99}
              hint="Facultatif, de 1 à 99."
            />
            <Select label="Poste" name="position" defaultValue="">
              <option value="">Non précisé</option>
              {Object.entries(POSITION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <FormError message={error} />
          <div>
            <SubmitButton pending={pending}>Ajouter le joueur</SubmitButton>
          </div>
        </form>
      ) : (
        <FormError message={error} />
      )}
    </main>
  );
}
