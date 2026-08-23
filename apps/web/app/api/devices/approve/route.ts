import { z } from 'zod'

import { fail, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const Approve = z.object({ userCode: z.string().min(4).max(20) })

/**
 * Approve a waiting device, as the signed-in person in a browser.
 *
 * This is the only step that needs a session, and it is the step that means
 * anything: the code the desktop is holding is inert until somebody who is
 * already signed in says yes to it.
 */
export const POST = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, Approve)

  const code = body.userCode.trim().toUpperCase()
  const pairing = await store().findPairingByUserCode(code)
  if (!pairing) return fail(404, 'not_found', 'that code has expired or was never issued')
  if (pairing.approvedAt) return fail(409, 'already_approved', 'that code has been used')

  const approved = await store().approvePairing(code, user.id)
  if (!approved) return fail(409, 'already_approved', 'that code has been used')

  return json({ name: pairing.name, platform: pairing.platform })
})
