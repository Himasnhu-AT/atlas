import { z } from 'zod'

import { isAdmin } from '@/lib/server/admin'
import { ForbiddenError, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

const ExcludeBody = z.object({ excluded: z.boolean() })

export const POST = route(async (request, context) => {
  const admin = await requireUser(request)
  if (!isAdmin(admin.email)) throw new ForbiddenError()

  const { userId } = await context.params
  const body = await parseBody(request, ExcludeBody)

  await store().adminSetLeaderboardExcluded(userId, body.excluded)
  return json({ success: true, userId, excluded: body.excluded })
})
