const KICKOFF = new Intl.DateTimeFormat("fr-FR", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** "sam. 21 nov. 2026, 15:00", in the browser's time zone. */
export function formatKickoff(iso: string): string {
  return KICKOFF.format(new Date(iso));
}

export function formatScore(team: number | null, opponent: number | null): string {
  return team === null || opponent === null ? "Score non saisi" : `${team} - ${opponent}`;
}
