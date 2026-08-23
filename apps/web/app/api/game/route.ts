import { json, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { gameStateFor } from '@/lib/server/xp'

/**
 * The whole game state in one request, the way `/api/progress` returns one
 * snapshot. Everything in it is derived server-side; nothing is ever sent up.
 */
export const GET = route(async (request) => {
  const user = await requireUser(request)
  return json(await gameStateFor(user.id))
})

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
