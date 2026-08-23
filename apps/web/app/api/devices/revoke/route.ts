import { z } from 'zod'

import { fail, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const Revoke = z.object({ deviceId: z.string().min(1).max(80) })

/**
 * Revoke a device.
 *
 * The store checks ownership in the same operation, so a device id belonging to
 * somebody else revokes nothing rather than being checked and then acted on.
 */
export const POST = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, Revoke)

  const revoked = await store().revokeDevice(user.id, body.deviceId)
  if (!revoked) return fail(404, 'not_found', 'no such device')

  return json({ revoked: true })
})
