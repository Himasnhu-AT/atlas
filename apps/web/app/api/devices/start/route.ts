import { z } from 'zod'

import { json, parseBody, preflight, route } from '@/lib/server/respond'
import { startPairing } from '@/lib/server/pairing'

const StartPairing = z.object({
  name: z.string().min(1).max(80),
  platform: z.string().min(1).max(40),
  appVersion: z.string().min(1).max(40),
})

/**
 * Begin pairing a device.
 *
 * Unauthenticated by necessity: the whole point is that the app has no
 * credential yet. It hands over nothing but a code that is worthless until a
 * signed-in browser approves it.
 */
export const POST = route(async (request) => {
  const body = await parseBody(request, StartPairing)
  const started = await startPairing(body)

  return json({
    deviceCode: started.deviceCode,
    userCode: started.userCode,
    verificationUri: `${origin(request)}/pair`,
    verificationUriComplete: `${origin(request)}/pair?code=${encodeURIComponent(started.userCode)}`,
    expiresAt: started.expiresAt,
    intervalSeconds: started.intervalSeconds,
  })
})

/**
 * Where to send the browser.
 *
 * Derived from the request rather than configured, so a self-hosted instance
 * sends people to itself. `Host` is client-controlled, but it is only ever
 * echoed back to the client that sent it, and the desktop already knows which
 * origin it asked.
 */
function origin(request: Request): string {
  return new URL(request.url).origin
}

export const OPTIONS = preflight
