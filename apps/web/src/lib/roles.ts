import type { Role } from "@/lib/api";

export const ROLE_LABELS: Record<Role, string> = {
  club_admin: "Administrateur du club",
  coach: "Entraîneur",
  player: "Joueur",
};
