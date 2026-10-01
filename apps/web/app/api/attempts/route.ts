import { NewAttempt } from '@atlas/core'

import { courseOfModule } from '@atlas/learning'

import { everyModule, exerciseIndex, manifest } from '@/lib/content'
import { accessFor, canOpen } from '@/lib/server/access'
import {
  BadRequestError,
  ForbiddenError,
  json,
  parseBody,
  preflight,
  route,
} from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import {
  awardsForAttempt,
  evaluateSeals,
  evaluateWeek,
  grant,
  levelCrossing,
  xpTotalFor,
} from '@/lib/server/xp'

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
  const located = exerciseIndex().get(body.exerciseId)
  if (!located) {
    throw new BadRequestError(`unknown exercise: ${body.exerciseId}`)
  }

  // Same gate as `/api/progress`. The desktop app bundles every exercise so it
  // can grade offline, which means this refuses the report rather than the work
  // — the honest limit of a gate on a client that already has the content.
  const module = everyModule().find((m) => m.id === located.moduleId)
  const course = module && courseOfModule(manifest, module.id)
  const access = await accessFor(user.id)
  if (module && course && !canOpen(access, course, module)) {
    throw new ForbiddenError(`${module.name} opens once you have finished what comes before it`)
  }

  const before = await xpTotalFor(user.id)

  await store().recordAttempt(user.id, {
    ...body,
    stdoutTail: body.stdoutTail?.slice(-4000),
  })
  await store().recordActivity(user.id, new Date().toISOString().slice(0, 10), 'attempt')

  // The attempt is recorded before the award is computed, so `failuresBeforePass`
  // already reflects this run. A failing run pays nothing; a passing one pays
  // once, ever, because the award key names the exercise and nothing else.
  const now = new Date().toISOString()
  let awarded = 0
  awarded += (await grant(user.id, await awardsForAttempt(user.id, body.exerciseId, body.passed), now))
    .points
  awarded += (await grant(user.id, await evaluateWeek(user.id), now)).points
  awarded += (await grant(user.id, await evaluateSeals(user.id), now)).points

  // Counted after the write, so this includes the run being answered: attempt
  // one is the first run, which is what the hint tiers assume.
  const stats = (await store().exerciseStats(user.id)).find(
    (row) => row.exerciseId === body.exerciseId,
  )

  // This was a 204 with no body while `browser-exercise.tsx` read `levelledTo`
  // off the response, so crossing a level by passing an exercise on the web
  // could never fire. `/api/progress` has always returned this shape.
  return json({
    awarded,
    levelledTo: levelCrossing(before, awarded),
    attemptNumber: (stats?.passes ?? 0) + (stats?.failures ?? 0),
  })
})

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
