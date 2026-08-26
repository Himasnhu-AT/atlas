import { z } from 'zod'

import { isAdmin } from '@/lib/server/admin'
import { fail, ForbiddenError, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const RevokeBody = z.object({
  userId: z.string().min(1),
  deviceId: z.string().min(1),
})

export const POST = route(async (request) => {
  const admin = await requireUser(request)
  if (!isAdmin(admin.email)) throw new ForbiddenError()

  const body = await parseBody(request, RevokeBody)
  const revoked = await store().revokeDevice(body.userId, body.deviceId)
  if (!revoked) return fail(404, 'not_found', 'device not found or already revoked')

  return json({ success: true, revoked: true })
})
