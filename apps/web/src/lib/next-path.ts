/**
 * The page to open after signing in, taken from ?next=.
 *
 * Only same-site paths are accepted, so a crafted link cannot send the user
 * to another website after they type their password.
 */
export function safeNextPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/dashboard";
  }
  return value;
}
