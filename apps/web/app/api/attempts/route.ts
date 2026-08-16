import { NewAttempt } from '@learn/core'

import { parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

/**
 * Test results posted by the desktop app.
 *
 * The verdict is recorded; the code never runs on a server. Grading happens on
 * the student's machine, which is the only place it needs to happen.
 */
export const POST = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, NewAttempt)

  await store().recordAttempt(user.id, {
    ...body,
    stdoutTail: body.stdoutTail?.slice(-4000),
  })
  await store().recordActivity(user.id, new Date().toISOString().slice(0, 10), 'attempt')

  return new Response(null, { status: 204 })
})
