import { UpdateGameSettings } from '@atlas/core'

import { json, parseBody, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { gameStateFor } from '@/lib/server/xp'

/** Leaderboard opt-in. Off by default, and reversible. */
export const PUT = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, UpdateGameSettings)

  await store().updateGame(user.id, { leaderboardOptIn: body.leaderboardOptIn })
  return json(await gameStateFor(user.id))
})

export const OPTIONS = preflight
