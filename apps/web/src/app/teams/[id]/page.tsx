import { Suspense } from "react";

import { TeamView } from "./team-view";

// The team id comes from the URL at request time, so the view streams in
// behind a Suspense boundary while the static shell is served first.
export default function TeamPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto w-full max-w-3xl flex-1 p-8 text-zinc-500">
          Chargement
        </main>
      }
    >
      <TeamView />
    </Suspense>
  );
}
