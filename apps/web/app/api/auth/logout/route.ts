import { json, route } from '@/lib/server/respond'
import { clearSessionCookie } from '@/lib/server/session'

export const POST = route(async () => {
  await clearSessionCookie()
  return json({ ok: true })
})
