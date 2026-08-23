/**
 * Streaks, and the freeze that keeps one bad day from ending a habit.
 *
 * `currentStreak` in `../progress` already computes a run of active days and is
 * correct; this adds the forgiving half. A streak with no way to survive a
 * missed day converts one bad Tuesday into a quit, which is the single most
 * reliable way to lose someone who was otherwise doing fine.
 *
 * Freezes are consumed lazily, at read time, computed from the activity log.
 * Nothing writes "you lost your streak" from a scheduled job, because a learner
 * who is offline for four days should not depend on a job having run, and a job
 * that has to run nightly for every user to stay correct is a job that will one
 * day not run.
 */

export interface ActivityLike {
  day: string
  lessonsTouched: number
  attempts: number
}

/** One freeze earned per completed week of streak, and never more than this. */
export const MAX_FREEZES = 3
const DAYS_PER_FREEZE = 7

export interface StreakState {
  /** Consecutive active days ending today or yesterday, freezes included. */
  days: number
  /** How many missed days the freezes covered inside the current run. */
  freezesSpent: number
  /** Freezes still in hand. */
  freezesAvailable: number
  /** The streak counted strictly, with no forgiveness. */
  rawDays: number
}

function previousDay(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() - 1)
  return date.toISOString().slice(0, 10)
}

/**
 * Walk back from today, allowing up to `freezes` single missed days.
 *
 * Yesterday still counts as the start, exactly as `currentStreak` has it: a
 * streak should not appear broken because the learner has not opened the app yet
 * this morning.
 *
 * Two missed days in a row end the run whatever is in hand. A freeze covers an
 * off day, not an off week, and spending two to bridge a gap would make "100 day
 * streak" mean something a reader would not recognise.
 */
export function streakState(
  days: ActivityLike[],
  today: string,
  earnedFreezes = 0,
): StreakState {
  const active = new Set(
    days.filter((d) => d.lessonsTouched > 0 || d.attempts > 0).map((d) => d.day),
  )
  if (active.size === 0) {
    return { days: 0, freezesSpent: 0, freezesAvailable: earnedFreezes, rawDays: 0 }
  }

  const start = active.has(today) ? today : previousDay(today)
  if (!active.has(start)) {
    return { days: 0, freezesSpent: 0, freezesAvailable: earnedFreezes, rawDays: 0 }
  }

  const budget = Math.min(earnedFreezes, MAX_FREEZES)
  let total = 0
  let rawDays = 0
  let spent = 0
  let raw = true
  let cursor = start

  for (;;) {
    if (active.has(cursor)) {
      total += 1
      if (raw) rawDays += 1
      cursor = previousDay(cursor)
      continue
    }

    // A gap. It can be bridged only if a freeze is in hand and the day before
    // it was itself active, so one freeze never spans two missed days.
    raw = false
    const before = previousDay(cursor)
    if (spent < budget && active.has(before)) {
      spent += 1
      total += 1
      cursor = before
      continue
    }
    break
  }

  return {
    days: total,
    freezesSpent: spent,
    freezesAvailable: Math.max(0, budget - spent),
    rawDays,
  }
}

/**
 * Freezes earned over a learner's whole history, one per seven active days.
 *
 * Earned from lifetime activity rather than from the current run, so a learner
 * who has shown up for months is not left defenceless the day after a streak
 * finally breaks.
 */
export function freezesEarned(days: ActivityLike[]): number {
  const active = days.filter((d) => d.lessonsTouched > 0 || d.attempts > 0).length
  return Math.min(MAX_FREEZES, Math.floor(active / DAYS_PER_FREEZE))
}
