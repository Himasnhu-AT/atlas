import { isoWeekOf, levelForXp } from '@atlas/core'

import { fail, json, preflight, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { serverDay, weekStart } from '@/lib/server/xp'

/**
 * The week's board.
 *
 * Opt-in and off by default, and refused outright to anyone who has not opted
 * in: a board you did not ask to be on is a different product from a board you
 * joined. Scored on when XP was received rather than when it was earned, so an
 * offline backlog drained on Monday cannot retroactively win last week.
 *
 * Deliberately small. A global ranking is motivating for the top decile and
 * discouraging for everyone else, which is the wrong trade for a learning tool.
 */
const LEAGUE_SIZE = 30

export const GET = route(async (request) => {
  const user = await requireUser(request)

  const game = await store().gameFor(user.id)
  if (!game.leaderboardOptIn) {
    return fail(403, 'not_opted_in', 'The leaderboard is opt-in. Join it from your ledger.')
  }

  const rows = await store().weeklyLeaderboard(weekStart(), LEAGUE_SIZE)

  return json({
    isoWeek: isoWeekOf(serverDay()),
    rows: rows.map((row) => ({
      displayName: row.displayName,
      level: levelForXp(row.totalXp),
      weeklyXp: row.weeklyXp,
      you: row.userId === user.id,
    })),
  })
})

export const OPTIONS = preflight
