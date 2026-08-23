import { UpdateLessonProgress, currentStreak, type ProgressSnapshot } from '@learn/core'
import { everyModule } from '@/lib/content'
import { BadRequestError, json, parseBody, route } from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

/**
 * Progress. The user id always comes from the session, never from the body.
 */

export const GET = route(async (request) => {
  const user = await requireUser(request)
  return json(await snapshotFor(user.id))
})

export const PUT = route(async (request) => {
  const user = await requireUser(request)
  const body = await parseBody(request, UpdateLessonProgress)

  // Lessons live in the content bundle, not the database, so validate the id
  // against the manifest. Without this a typo writes an orphan row nobody ever
  // notices.
  const module = everyModule().find((m) => m.id === body.moduleId)
  const lesson = module?.lessons.find((l) => l.id === body.lessonId)
  if (!module || !lesson) {
    throw new BadRequestError(`unknown lesson: ${body.lessonId}`)
  }

  const now = new Date().toISOString()
  const existing = (await store().progressFor(user.id)).lessons.find(
    (row) => row.lessonId === body.lessonId,
  )

  await store().upsertLessonProgress(user.id, {
    lessonId: body.lessonId,
    moduleId: body.moduleId,
    status: body.status,
    secondsSpent: (existing?.secondsSpent ?? 0) + (body.secondsSpent ?? 0),
    startedAt: existing?.startedAt ?? now,
    completedAt: body.status === 'completed' ? (existing?.completedAt ?? now) : undefined,
  })

  await store().recordActivity(user.id, now.slice(0, 10), 'lesson')
  await recomputeModule(user.id, body.moduleId)

  return json(await snapshotFor(user.id))
})

/** Module rollup is derived, so it can never drift from the lesson rows. */
async function recomputeModule(userId: string, moduleId: string): Promise<void> {
  const module = everyModule().find((m) => m.id === moduleId)
  if (!module) return

  const snapshot = await store().progressFor(userId)
  const lessonIds = new Set(module.lessons.map((lesson) => lesson.id))
  const rows = snapshot.lessons.filter((row) => lessonIds.has(row.lessonId))
  const completed = rows.filter((row) => row.status === 'completed').length

  const now = new Date().toISOString()
  const previous = snapshot.modules.find((row) => row.moduleId === moduleId)

  await store().upsertModuleProgress(userId, {
    moduleId,
    status:
      completed === module.lessons.length && module.lessons.length > 0
        ? 'completed'
        : rows.length > 0
          ? 'in_progress'
          : 'available',
    lessonsCompleted: completed,
    lessonsTotal: module.lessons.length,
    startedAt: previous?.startedAt ?? now,
    completedAt:
      completed === module.lessons.length && module.lessons.length > 0
        ? (previous?.completedAt ?? now)
        : undefined,
  })
}

async function snapshotFor(userId: string): Promise<ProgressSnapshot> {
  const snapshot = await store().progressFor(userId)
  return {
    ...snapshot,
    streakDays: currentStreak(snapshot.activity, new Date().toISOString().slice(0, 10)),
  }
}
