/**
 * The weekly target: a goal the learner sets for themselves.
 *
 * This replaces a daily streak, and the reason is worth writing down because a
 * streak is the obvious thing to build and this platform deliberately does not
 * have one.
 *
 * A daily streak fits a product that is infinite and daily-cadenced. A course
 * whose lessons take thirty to sixty minutes is neither: the honest learner who
 * does two hours on Saturday is punished, and the one who wants the number
 * intact is pushed toward whatever the cheapest qualifying action is. The
 * measured asymmetry is the other half of it. A streak motivates while it is
 * alive and punishes disproportionately when it breaks, so the mechanic's own
 * best case is smaller than its worst case.
 *
 * Codecademy retired daily streaks for learner-set weekly targets and published
 * the reason. Exercism refuses streaks past five days on the grounds that people
 * should be allowed days off. Both are right for this shape of product.
 *
 * A target is self-authored, so missing it is information rather than a
 * punishment, and a week absorbs a bad Tuesday structurally instead of needing a
 * freeze item to forgive one.
 */

export interface ActivityLike {
  day: string
  lessonsTouched: number
  attempts: number
}

export const MIN_TARGET = 1
export const MAX_TARGET = 7
export const DEFAULT_TARGET = 3

export function clampTarget(days: number): number {
  if (!Number.isFinite(days)) return DEFAULT_TARGET
  return Math.min(MAX_TARGET, Math.max(MIN_TARGET, Math.round(days)))
}

/** Monday of the ISO week containing `day`, as `YYYY-MM-DD`. */
export function weekStartOf(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  const weekday = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() - (weekday - 1))
  return date.toISOString().slice(0, 10)
}

function shiftWeeks(weekStart: string, weeks: number): string {
  const date = new Date(`${weekStart}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + weeks * 7)
  return date.toISOString().slice(0, 10)
}

function activeDays(days: ActivityLike[]): Set<string> {
  return new Set(days.filter((d) => d.lessonsTouched > 0 || d.attempts > 0).map((d) => d.day))
}

function daysActiveInWeek(active: Set<string>, weekStart: string): number {
  let count = 0
  for (let i = 0; i < 7; i += 1) {
    const date = new Date(`${weekStart}T00:00:00Z`)
    date.setUTCDate(date.getUTCDate() + i)
    if (active.has(date.toISOString().slice(0, 10))) count += 1
  }
  return count
}

export interface WeeklyProgress {
  /** Days the learner asked of themselves. */
  target: number
  /** Days worked so far this week. */
  daysActive: number
  met: boolean
  weekStart: string
  /** Consecutive earlier weeks whose target was met, this week excluded. */
  weeksInARow: number
  /** Longest run of met weeks, ever. */
  bestWeeks: number
}

/**
 * This week against the target, plus the run of weeks behind it.
 *
 * The current week is excluded from `weeksInARow` because it is not over. A
 * count that includes a week still in progress would drop back to zero on
 * Monday morning, which is the streak-anxiety failure in weekly clothing.
 */
export function weeklyProgress(
  days: ActivityLike[],
  today: string,
  target: number,
): WeeklyProgress {
  const goal = clampTarget(target)
  const active = activeDays(days)
  const thisWeek = weekStartOf(today)
  const daysActive = daysActiveInWeek(active, thisWeek)

  let weeksInARow = 0
  for (let back = 1; back <= 520; back += 1) {
    const week = shiftWeeks(thisWeek, -back)
    if (daysActiveInWeek(active, week) >= goal) weeksInARow += 1
    else break
  }

  // Every week that has any activity at all, so a best-ever run can be found
  // without walking the calendar back to the epoch.
  const weeks = [...new Set([...active].map(weekStartOf))].sort()
  let best = 0
  let run = 0
  let previous: string | undefined
  for (const week of weeks) {
    if (daysActiveInWeek(active, week) < goal) {
      run = 0
      previous = week
      continue
    }
    run = previous !== undefined && shiftWeeks(previous, 1) === week ? run + 1 : 1
    best = Math.max(best, run)
    previous = week
  }

  return {
    target: goal,
    daysActive,
    met: daysActive >= goal,
    weekStart: thisWeek,
    weeksInARow,
    bestWeeks: best,
  }
}

/**
 * The most one day can contribute to a week's board score.
 *
 * Sized from the content: the heaviest module in the catalogue is worth about
 * 735 xp end to end, so this is roughly three of them in a single day. Nobody
 * reaches it by studying. It exists because grading is client-side and has to
 * stay that way, so a determined person can post a pass for every exercise in
 * the catalogue in a few seconds, and a public board is the one place that
 * makes doing so visible and demoralising to everyone else.
 */
export const DAILY_BOARD_CAP = 2200

/**
 * A week's board score, with each day clamped.
 *
 * The clamp is on the board, not on the ledger. Withholding xp somebody
 * genuinely earned would punish the rare learner who really did clear three
 * modules on a Saturday, and they are far more common than the griefer. Their
 * level, their seals and their own totals are all untouched; only their
 * standing in one week's ranking is bounded.
 *
 * `byDay` maps a day (`YYYY-MM-DD`) to the xp awarded on it, keyed on when the
 * award was received rather than when it was earned, so an offline backlog
 * drained on Monday cannot retroactively win last week.
 */
export function boardScore(byDay: Record<string, number>, cap = DAILY_BOARD_CAP): number {
  let total = 0
  for (const points of Object.values(byDay)) {
    total += Math.min(Math.max(0, points), cap)
  }
  return total
}
