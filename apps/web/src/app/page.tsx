"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ApiStatus } from "@/components/api-status";
import { useAuth } from "@/components/auth-provider";

export default function Home() {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">
          AI Football Analytics
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Analysez vos matchs à partir de vos vidéos.
        </p>
      </div>
      <div className="flex gap-3">
        <Link
          href="/register"
          className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800"
        >
          Créer un compte
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-zinc-300 px-4 py-2 font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Se connecter
        </Link>
      </div>
      <ApiStatus />
    </main>
  );
}
