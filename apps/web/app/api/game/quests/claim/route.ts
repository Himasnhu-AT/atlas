import { ClaimQuest } from '@atlas/core'

import { json, parseBody, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { claimQuest, gameStateFor } from '@/lib/server/xp'

/**
 * Claim a completed quest.
 *
 * The body carries a claim key and nothing else. No point value, because the
 * server decides what a quest is worth, and no proof of completion, because the
 * server re-derives that from the same rows it would have used anyway. A key
 * naming a quest that was never offered, or one that is not finished, pays zero
 * rather than erroring: the client asked a reasonable question and the answer is
 * no.
 */
export const POST = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, ClaimQuest)

  const awarded = await claimQuest(user.id, body.claimKey)
  return json({ awarded, game: await gameStateFor(user.id) })
})

export const OPTIONS = preflight
