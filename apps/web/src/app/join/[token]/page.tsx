import { Suspense } from "react";

import { JoinView } from "./join-view";

export default function JoinPage() {
  return (
    <Suspense
      fallback={
        <main className="flex flex-1 items-center justify-center p-8 text-zinc-500">
          Chargement
        </main>
      }
    >
      <JoinView />
    </Suspense>
  );
}
