/**
 * When a session token is worth replacing.
 *
 * Here rather than in the web app's `lib/server/` because it is arithmetic over
 * two numbers, it holds no secret, and that directory imports `server-only` and
 * so cannot be unit tested. Signing and verifying stay behind the boundary,
 * where the key is; deciding that a token is getting on is not a secret.
 */

/**
 * True when `expiresAt` is past the halfway point of a token's life.
 *
 * The window slides. A client in regular use always carries a token with more
 * than half its life left, so a paired desktop never meets the expiry it was
 * issued with, while one that has been closed for a month still expires on
 * schedule. Without this a desktop is signed out on the thirtieth day whatever
 * it was doing on the twenty-ninth, and the first the learner hears of it is
 * their queued work refusing to sync.
 *
 * Refreshing on every request instead would mint a token per action and stop
 * the token ageing at all, which is a thirty day expiry that never arrives.
 *
 * An already expired token returns false: it is not stale, it is finished, and
 * renewing it would turn an expiry into a formality.
 */
export function tokenNeedsRefresh(expiresAt: number, lifetimeMs: number, now: number): boolean {
  const remaining = expiresAt - now
  return remaining > 0 && remaining < lifetimeMs / 2
}
