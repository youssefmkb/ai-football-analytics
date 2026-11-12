import { ApiStatus } from "@/components/api-status";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 p-8">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">
          AI Football Analytics
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Socle technique en place. État des services :
        </p>
      </div>
      <ApiStatus />
    </main>
  );
}
