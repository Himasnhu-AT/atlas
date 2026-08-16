import type { ModuleProgress, ModuleStatus, ProgressSnapshot } from './types'

/**
 * Progress arithmetic, shared so the web dashboard and the desktop navigator
 * cannot disagree about what "done" means.
 *
 * Pure functions over a snapshot. The server remains the authority on what a
 * student may open; these mirror its rules so the UI can render without a round
 * trip.
 */

export function moduleStatus(
  moduleId: string,
  prerequisites: string[],
  snapshot: ProgressSnapshot,
): ModuleStatus {
  const completed = new Set(
    snapshot.modules.filter((m) => m.status === 'completed').map((m) => m.moduleId),
  )

  if (!prerequisites.every((id) => completed.has(id))) return 'locked'

  const record = snapshot.modules.find((m) => m.moduleId === moduleId)
  if (!record) return 'available'
  if (record.status === 'locked') return 'available'
  return record.status
}

export function isLessonComplete(lessonId: string, snapshot: ProgressSnapshot): boolean {
  return snapshot.lessons.some((l) => l.lessonId === lessonId && l.status === 'completed')
}

export function modulePercent(progress: ModuleProgress | undefined): number {
  if (!progress || progress.lessonsTotal === 0) return 0
  return Math.round((progress.lessonsCompleted / progress.lessonsTotal) * 100)
}

export function overallPercent(snapshot: ProgressSnapshot): number {
  const total = snapshot.modules.reduce((sum, m) => sum + m.lessonsTotal, 0)
  if (total === 0) return 0
  const done = snapshot.modules.reduce((sum, m) => sum + m.lessonsCompleted, 0)
  return Math.round((done / total) * 100)
}

/**
 * The lesson to resume: the most recently started incomplete one, falling back
 * to the first lesson of the first unfinished module.
 */
export function resumeLessonId(snapshot: ProgressSnapshot): string | undefined {
  const inProgress = snapshot.lessons
    .filter((l) => l.status === 'in_progress')
    .sort((a, b) => (b.startedAt ?? '').localeCompare(a.startedAt ?? ''))

  return inProgress[0]?.lessonId
}

/**
 * Consecutive days of activity ending today or yesterday.
 *
 * Yesterday still counts: a streak should not break because the student has not
 * opened the app yet this morning.
 */
export function currentStreak(days: ActivityLike[], today: string): number {
  const active = new Set(
    days.filter((d) => d.lessonsTouched > 0 || d.attempts > 0).map((d) => d.day),
  )
  if (active.size === 0) return 0

  const start = active.has(today) ? today : previousDay(today)
  if (!active.has(start)) return 0

  let streak = 0
  let cursor = start
  while (active.has(cursor)) {
    streak += 1
    cursor = previousDay(cursor)
  }
  return streak
}

interface ActivityLike {
  day: string
  lessonsTouched: number
  attempts: number
}

/** Dates are plain `YYYY-MM-DD` strings, compared in UTC to avoid drift. */
function previousDay(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() - 1)
  return date.toISOString().slice(0, 10)
}
