"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Check = "loading" | "ok" | "error";

async function probe(path: string): Promise<Check> {
  try {
    const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
    return response.ok ? "ok" : "error";
  } catch {
    return "error";
  }
}

const LABELS: Record<Check, string> = {
  loading: "Vérification en cours",
  ok: "Opérationnel",
  error: "Injoignable",
};

const COLORS: Record<Check, string> = {
  loading: "bg-zinc-400",
  ok: "bg-emerald-500",
  error: "bg-red-500",
};

function Row({ name, state }: { name: string; state: Check }) {
  return (
    <li className="flex items-center justify-between gap-6 py-2">
      <span>{name}</span>
      <span className="flex items-center gap-2 text-sm">
        <span
          aria-hidden
          className={`inline-block size-2.5 rounded-full ${COLORS[state]}`}
        />
        {LABELS[state]}
      </span>
    </li>
  );
}

export function ApiStatus() {
  const [api, setApi] = useState<Check>("loading");
  const [database, setDatabase] = useState<Check>("loading");

  useEffect(() => {
    let cancelled = false;
    probe("/api/v1/health").then((state) => {
      if (!cancelled) setApi(state);
    });
    probe("/api/v1/health/db").then((state) => {
      if (!cancelled) setDatabase(state);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ul className="w-full max-w-sm divide-y divide-zinc-200 dark:divide-zinc-800">
      <Row name="API" state={api} />
      <Row name="Base de données" state={database} />
    </ul>
  );
}
