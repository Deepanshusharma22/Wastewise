/**
 * Server-side helper: is the API running in LOCAL_MODE?
 *
 * Used by the auth callback so the right token exchange happens (local JWT vs
 * Supabase). The answer is cached for a few seconds per server instance; a wrong
 * guess only costs one extra round-trip, never a failed login.
 */
const API_URL = (process.env.API_URL || "http://localhost:8000").replace(/\/$/, "");
let cache: { value: boolean; at: number } | null = null;

export async function isLocalMode(): Promise<boolean> {
  if (cache && Date.now() - cache.at < 30_000) return cache.value;
  let value = false;
  try {
    const res = await fetch(`${API_URL}/api/v1/local-info`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    value = res.ok;
  } catch {
    value = false;
  }
  cache = { value, at: Date.now() };
  return value;
}
