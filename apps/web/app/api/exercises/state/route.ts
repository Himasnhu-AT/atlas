import { SaveExerciseCode } from '@learn/core'

import { BadRequestError, json, parseBody, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

/**
 * The student's working buffer, so closing the app does not lose their work.
 */

export const GET = route(async (request) => {
  const user = await requireUser(request)
  const exerciseId = new URL(request.url).searchParams.get('exerciseId')
  if (!exerciseId) throw new BadRequestError('exerciseId is required')

  return json(await store().exerciseState(user.id, exerciseId))
})

export const PUT = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, SaveExerciseCode)

  const existing = await store().exerciseState(user.id, body.exerciseId)

  await store().saveExerciseState(user.id, {
    exerciseId: body.exerciseId,
    currentCode: body.currentCode,
    // Once a student has looked at the reference, that stays true. Clearing it
    // would let the flag be reset by an ordinary autosave.
    peekedReferenceAt:
      existing?.peekedReferenceAt ?? (body.peeked ? new Date().toISOString() : undefined),
    updatedAt: new Date().toISOString(),
  })

  return new Response(null, { status: 204 })
})

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
