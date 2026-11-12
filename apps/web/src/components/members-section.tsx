"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { Field, FormError, Select, SubmitButton } from "@/components/form";
import type { Role } from "@/lib/api";
import { errorMessage } from "@/lib/messages";
import { ROLE_LABELS } from "@/lib/roles";

type Member = {
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
  is_self: boolean;
};

type Invitation = {
  id: string;
  role: Role;
  label: string | null;
  expires_at: string;
};

const EXPIRY = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" });
const SMALL_SELECT =
  "rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";
const LAST_ADMIN = "Le club doit garder au moins un administrateur.";

function inviteLink(token: string): string {
  return `${window.location.origin}/join/${token}`;
}

export function MembersSection() {
  const { api, reloadMe } = useAuth();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [link, setLink] = useState<{ id: string; url: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(
    () =>
      Promise.all([
        api<Member[]>("/organizations/current/members"),
        api<Invitation[]>("/organizations/current/invitations"),
      ]),
    [api],
  );

  const refresh = useCallback(async () => {
    const [loadedMembers, loadedInvitations] = await fetchAll();
    setMembers(loadedMembers);
    setInvitations(loadedInvitations);
  }, [fetchAll]);

  useEffect(() => {
    let cancelled = false;
    fetchAll()
      .then(([loadedMembers, loadedInvitations]) => {
        if (cancelled) return;
        setMembers(loadedMembers);
        setInvitations(loadedInvitations);
      })
      .catch((failure) => {
        if (!cancelled) setError(errorMessage(failure));
      });
    return () => {
      cancelled = true;
    };
  }, [fetchAll]);

  async function onInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setPending(true);
    setError(null);
    setCopied(false);
    try {
      const created = await api<Invitation & { token: string }>(
        "/organizations/current/invitations",
        {
          method: "POST",
          body: { role: String(form.get("role")), label: String(form.get("label") ?? "") },
        },
      );
      setLink({ id: created.id, url: inviteLink(created.token) });
      formElement.reset();
      await refresh();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setPending(false);
    }
  }

  async function onCopy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
    } catch {
      setError("La copie a échoué. Sélectionnez le lien et copiez-le à la main.");
    }
  }

  async function run(action: () => Promise<unknown>, afterwards?: () => Promise<void>) {
    setError(null);
    try {
      await action();
      await refresh();
      if (afterwards) await afterwards();
    } catch (failure) {
      setError(errorMessage(failure, { 409: LAST_ADMIN }));
    }
  }

  function onRoleChange(member: Member, role: Role) {
    run(
      () =>
        api(`/organizations/current/members/${member.user_id}`, {
          method: "PATCH",
          body: { role },
        }),
      // Changing your own role changes what this page may show.
      member.is_self ? reloadMe : undefined,
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">Membres du club</h2>
        {members === null && !error ? (
          <p className="text-sm text-zinc-500">Chargement</p>
        ) : null}
        {members ? (
          <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
            {members.map((member) => (
              <li
                key={member.user_id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
              >
                <span>
                  <span className="font-medium">
                    {member.full_name}
                    {member.is_self ? " (vous)" : ""}
                  </span>
                  <span className="block text-sm text-zinc-500">{member.email}</span>
                </span>
                <span className="flex items-center gap-3">
                  <select
                    aria-label={`Rôle de ${member.full_name}`}
                    value={member.role}
                    onChange={(event) => onRoleChange(member, event.target.value as Role)}
                    className={SMALL_SELECT}
                  >
                    {Object.entries(ROLE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  {member.is_self ? null : (
                    <button
                      type="button"
                      aria-label={`Retirer ${member.full_name} du club`}
                      onClick={() =>
                        run(() =>
                          api(`/organizations/current/members/${member.user_id}`, {
                            method: "DELETE",
                          }),
                        )
                      }
                      className="text-sm text-red-700 underline dark:text-red-400"
                    >
                      Retirer
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <form onSubmit={onInvite} className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Inviter quelqu&apos;un</h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Un lien est créé. Envoyez-le à la personne : il est valable 7 jours et ne
          sert qu&apos;une fois.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Rôle" name="role" defaultValue="player">
            <option value="player">{ROLE_LABELS.player}</option>
            <option value="coach">{ROLE_LABELS.coach}</option>
          </Select>
          <Field
            label="Pour qui"
            name="label"
            maxLength={120}
            hint="Facultatif, pour vous y retrouver."
          />
        </div>
        <div>
          <SubmitButton pending={pending}>Créer le lien</SubmitButton>
        </div>
      </form>

      {link ? (
        <div className="flex flex-col gap-2 rounded-lg border border-emerald-600/40 bg-emerald-50 p-4 dark:bg-emerald-950/40">
          <p className="text-sm font-medium">
            Lien à envoyer. Il ne sera plus affiché ensuite.
          </p>
          <input
            readOnly
            aria-label="Lien d'invitation"
            value={link.url}
            onFocus={(event) => event.currentTarget.select()}
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onCopy}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-white dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              Copier le lien
            </button>
            {copied ? (
              <span role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
                Lien copié.
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {invitations.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">Invitations en attente</h3>
          <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 text-sm dark:divide-zinc-800 dark:border-zinc-800">
            {invitations.map((invitation) => (
              <li
                key={invitation.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-2"
              >
                <span>
                  {ROLE_LABELS[invitation.role]}
                  {invitation.label ? ` · ${invitation.label}` : ""}
                  <span className="text-zinc-500">
                    {" "}
                    · expire le {EXPIRY.format(new Date(invitation.expires_at))}
                  </span>
                </span>
                <button
                  type="button"
                  aria-label={`Annuler l'invitation ${invitation.label ?? ROLE_LABELS[invitation.role]}`}
                  onClick={() =>
                    run(async () => {
                      await api(`/organizations/current/invitations/${invitation.id}`, {
                        method: "DELETE",
                      });
                      // A cancelled link must not stay on screen, ready to be sent.
                      if (link?.id === invitation.id) setLink(null);
                    })
                  }
                  className="text-red-700 underline dark:text-red-400"
                >
                  Annuler
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <FormError message={error} />
    </section>
  );
}
