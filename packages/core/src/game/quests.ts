/**
 * The day's quests, chosen deterministically.
 *
 * There is no scheduler and no quest table. The three offered on a given day are
 * a pure function of the user id and the server's date, and their progress is
 * computed from data the API already writes: activity days, lesson rows and
 * attempt rows. Nothing is stored until a quest is claimed, and a claim is just
 * a row in the XP ledger keyed `quest:<id>:<day>`.
 *
 * That is worth more than it sounds. A cron job that assigns quests at midnight
 * has to pick a midnight, has to run, has to backfill users it missed, and has
 * to be reasoned about every time the schema changes. This has none of those and
 * cannot drift, because there is no state to drift.
 */

export type QuestPeriod = 'daily' | 'weekly'

export interface Quest {
  id: string
  period: QuestPeriod
  title: string
  /** How many of the thing are needed. */
  target: number
  metric: QuestMetric
}

export type QuestMetric =
  | 'lessons_completed'
  | 'exercises_passed'
  | 'exercises_passed_unaided'
  | 'exercises_passed_first_run'
  | 'modules_completed'
  | 'active_days'

const DAILY: readonly Quest[] = [
  { id: 'read-one', period: 'daily', title: 'Finish a lesson', target: 1, metric: 'lessons_completed' },
  { id: 'read-two', period: 'daily', title: 'Finish two lessons', target: 2, metric: 'lessons_completed' },
  { id: 'pass-one', period: 'daily', title: 'Pass an exercise', target: 1, metric: 'exercises_passed' },
  { id: 'pass-two', period: 'daily', title: 'Pass two exercises', target: 2, metric: 'exercises_passed' },
  {
    id: 'unaided',
    period: 'daily',
    title: 'Pass one without revealing the reference',
    target: 1,
    metric: 'exercises_passed_unaided',
  },
  {
    id: 'first-run',
    period: 'daily',
    title: 'Pass one on the first run',
    target: 1,
    metric: 'exercises_passed_first_run',
  },
]

const WEEKLY: readonly Quest[] = [
  { id: 'week-five-exercises', period: 'weekly', title: 'Pass five exercises this week', target: 5, metric: 'exercises_passed' },
  { id: 'week-three-days', period: 'weekly', title: 'Work on three days this week', target: 3, metric: 'active_days' },
  { id: 'week-one-module', period: 'weekly', title: 'Finish a module this week', target: 1, metric: 'modules_completed' },
]

export const DAILY_QUEST_COUNT = 3

/**
 * A small, stable string hash.
 *
 * FNV-1a, because the pick has to be identical in the API, the web app and the
 * desktop app, and has to stay identical across Node versions and runtimes.
 * Anything reaching for `Math.random` or a platform hash would make the day's
 * quests disagree between two surfaces showing them side by side.
 */
export function hashString(input: string): number {
  let hash = 0x811c9dc5
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash >>> 0
}

/** Deterministic sample without replacement, seeded by the string. */
function pick<T>(pool: readonly T[], count: number, seed: string): T[] {
  const remaining = [...pool]
  const chosen: T[] = []
  for (let i = 0; i < count && remaining.length > 0; i += 1) {
    const index = hashString(`${seed}:${i}`) % remaining.length
    chosen.push(remaining.splice(index, 1)[0]!)
  }
  return chosen
}

/**
 * The quests on offer for one user on one day.
 *
 * `day` is a `YYYY-MM-DD` the server assigned. Passing a client date here would
 * let a learner roll their clock back and draw a fresh set.
 */
export function questsForDay(userId: string, day: string): Quest[] {
  return pick(DAILY, DAILY_QUEST_COUNT, `${userId}:${day}`)
}

/** The week's quest. ISO weeks, so it turns over on a Monday. */
export function questForWeek(userId: string, isoWeek: string): Quest {
  return pick(WEEKLY, 1, `${userId}:${isoWeek}`)[0]!
}

/** `2026-W35`. The key a weekly quest is claimed against. */
export function isoWeekOf(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  // Thursday decides the year an ISO week belongs to.
  const thursday = new Date(date)
  thursday.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(thursday.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((thursday.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7)
  return `${thursday.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

/** Counts the metrics quests read, over whatever window the caller selected. */
export interface QuestCounts {
  lessons_completed: number
  exercises_passed: number
  exercises_passed_unaided: number
  exercises_passed_first_run: number
  modules_completed: number
  active_days: number
}

export const EMPTY_COUNTS: QuestCounts = {
  lessons_completed: 0,
  exercises_passed: 0,
  exercises_passed_unaided: 0,
  exercises_passed_first_run: 0,
  modules_completed: 0,
  active_days: 0,
}

export interface QuestProgress {
  quest: Quest
  progress: number
  complete: boolean
}

export function questProgress(quest: Quest, counts: QuestCounts): QuestProgress {
  const progress = Math.min(counts[quest.metric] ?? 0, quest.target)
  return { quest, progress, complete: progress >= quest.target }
}
