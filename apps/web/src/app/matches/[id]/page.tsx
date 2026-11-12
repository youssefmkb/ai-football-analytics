import { Suspense } from "react";

import { MatchView } from "./match-view";

export default function MatchPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto w-full max-w-3xl flex-1 p-8 text-zinc-500">
          Chargement
        </main>
      }
    >
      <MatchView />
    </Suspense>
  );
}
