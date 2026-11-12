import { ApiError } from "@/lib/api";

/** Turn an API failure into a sentence the user can act on. */
export function errorMessage(error: unknown, byStatus: Record<number, string> = {}): string {
  if (error instanceof ApiError) {
    if (byStatus[error.status]) return byStatus[error.status];
    if (error.status === 422) return "Certains champs sont invalides. Vérifiez votre saisie.";
    return "Le serveur a refusé la demande. Réessayez dans un instant.";
  }
  return "Le serveur est injoignable. Vérifiez qu'il est démarré.";
}
