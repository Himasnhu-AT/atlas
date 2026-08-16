import { json, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'

export const GET = route(async (request) => json(await requireUser(request)))
