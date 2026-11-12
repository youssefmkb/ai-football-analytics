export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Role = "club_admin" | "coach" | "player";

export type Me = {
  user: { id: string; email: string; full_name: string };
  membership: {
    organization_id: string;
    organization_name: string;
    role: Role;
  } | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = "";
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // Not JSON: keep the generic message.
  }
  return new ApiError(response.status, detail || `HTTP ${response.status}`);
}

/** Call the API. Cookies are always sent so the refresh token reaches /auth. */
export async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  const response = await fetch(`${API_URL}/api/v1${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Exchange the refresh cookie for a new access token.
 *
 * Calls are deduplicated: the API rotates the refresh token on every use and
 * treats a replayed token as stolen, so two parallel refreshes would log the
 * user out everywhere.
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = request<{ access_token: string }>("/auth/refresh", {
      method: "POST",
    })
      .then((data) => data.access_token)
      .catch(() => null)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}
