import { UpdateGameSettings, clampTarget } from '@atlas/core'

import { json, parseBody, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { evaluateWeek, gameStateFor, grant } from '@/lib/server/xp'

/**
 * The two things a learner decides for themselves: the weekly target, and
 * whether they are on the board at all.
 *
 * Setting a target marks it as chosen, which is what lets the surface stop
 * presenting a default as though it were a goal. Both are reversible and
 * neither is on by default.
 */
export const PUT = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, UpdateGameSettings)

  const patch: Parameters<ReturnType<typeof store>['updateGame']>[1] = {}
  if (body.leaderboardOptIn !== undefined) patch.leaderboardOptIn = body.leaderboardOptIn
  if (body.weeklyTarget !== undefined) {
    patch.weeklyTarget = clampTarget(body.weeklyTarget)
    patch.weeklyTargetChosen = true
  }

  await store().updateGame(user.id, patch)

  // Lowering a target can meet it outright. Paying only on the next lesson
  // would leave the week showing "met" beside an award that had not arrived.
  // The award key is the week, so this cannot pay twice however often the
  // target is changed.
  if (patch.weeklyTarget !== undefined) {
    await grant(user.id, await evaluateWeek(user.id), new Date().toISOString())
  }

  return json(await gameStateFor(user.id))
})

export const OPTIONS = preflight
