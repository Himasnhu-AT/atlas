import { z } from 'zod'

import { isAdmin } from '@/lib/server/admin'
import { ForbiddenError, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const AwardBody = z.object({
  points: z.number().int().min(1).max(10000),
  reason: z.string().min(1).max(200).default('Admin adjustment'),
})

export const POST = route(async (request, context) => {
  const admin = await requireUser(request)
  if (!isAdmin(admin.email)) throw new ForbiddenError()

  const { userId } = await context.params
  const body = await parseBody(request, AwardBody)

  const points = await store().adminAwardXp(userId, body.points, body.reason)
  return json({ success: true, userId, pointsAwarded: points })
})
