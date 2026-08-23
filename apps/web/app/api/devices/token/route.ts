import { z } from 'zod'

import { fail, json, parseBody, preflight, route } from '@/lib/server/respond'
import { collectPairing } from '@/lib/server/pairing'
import { createToken } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const CollectToken = z.object({ deviceCode: z.string().min(16).max(200) })

/**
 * Collect the token for an approved pairing.
 *
 * Also unauthenticated: possession of the device code is the credential, and it
 * was never shown to anyone. `pending` and `expired` are 200s rather than
 * errors, because the app polling here is asking a reasonable question and
 * "not yet" is a reasonable answer.
 */
export const POST = route(async (request) => {
  const body = await parseBody(request, CollectToken)
  const result = await collectPairing(body.deviceCode)

  if (result.status !== 'approved') return json({ status: result.status })

  const user = await store().findUserById(result.userId)
  if (!user) return fail(410, 'gone', 'that account no longer exists')

  return json({
    status: 'approved',
    // Scoped to the device, so revoking it actually works.
    token: createToken(result.userId, result.deviceId),
    deviceId: result.deviceId,
    email: user.email,
    displayName: user.displayName,
  })
})

export const OPTIONS = preflight
