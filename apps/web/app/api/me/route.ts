import { json, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'

export const GET = route(async (request) => json(await requireUser(request)))

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
