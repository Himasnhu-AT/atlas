import { NewAttempt } from '@atlas/core'

import { exerciseIndex } from '@/lib/content'
import { BadRequestError, parseBody, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { awardsForAttempt, evaluateSeals, evaluateWeek, grant } from '@/lib/server/xp'

/**
 * Test results posted by the desktop app.
 *
 * The verdict is recorded; the code never runs on a server. Grading happens on
 * the student's machine, which is the only place it needs to happen.
 */
export const POST = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, NewAttempt)

  // Exercises live in the content bundle, not the database, so validate the id
  // against the manifest. `/api/progress` has always done this for lessons and
  // this route did it for nothing: any string was a valid exercise, which wrote
  // rows nobody could trace back to content and which will be worth XP shortly.
  if (!exerciseIndex().has(body.exerciseId)) {
    throw new BadRequestError(`unknown exercise: ${body.exerciseId}`)
  }

  await store().recordAttempt(user.id, {
    ...body,
    stdoutTail: body.stdoutTail?.slice(-4000),
  })
  await store().recordActivity(user.id, new Date().toISOString().slice(0, 10), 'attempt')

  // The attempt is recorded before the award is computed, so `failuresBeforePass`
  // already reflects this run. A failing run pays nothing; a passing one pays
  // once, ever, because the award key names the exercise and nothing else.
  const now = new Date().toISOString()
  const awards = await awardsForAttempt(user.id, body.exerciseId, body.passed)
  await grant(user.id, awards, now)
  await grant(user.id, await evaluateWeek(user.id), now)
  await grant(user.id, await evaluateSeals(user.id), now)

  return new Response(null, { status: 204 })
})

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
