import { UpdateLessonProgress, currentStreak, type ProgressSnapshot } from '@atlas/core'
import { courseOfModule } from '@atlas/learning'

import { everyModule, manifest } from '@/lib/content'
import { accessFor, canOpen } from '@/lib/server/access'
import {
  BadRequestError,
  ForbiddenError,
  json,
  parseBody,
  preflight,
  route,
} from '@/lib/server/respond'
import { requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import {
  awardsForLessonCompletion,
  evaluateSeals,
  evaluateWeek,
  grant,
} from '@/lib/server/xp'

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

  // The gate applies to progress, not only to the body. Hiding the button is UI
  // and the endpoint is the boundary: without this a free account can mark a
  // members-only lesson complete and be paid for content it was never sent.
  const course = courseOfModule(manifest, module.id)
  const access = await accessFor(user.id)
  if (course && !canOpen(access, course, module)) {
    throw new ForbiddenError(`${module.name} is not included in your plan`)
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

  // XP is granted here, from the event the server just recorded, never from
  // anything the client sent. Only a completion pays, and the award key means
  // toggling a lesson off and on again pays nothing further.
  let awarded = 0
  if (body.status === 'completed') {
    const awards = await awardsForLessonCompletion(user.id, body.lessonId, body.moduleId)
    awarded += (await grant(user.id, awards, now)).points
    awarded += (await grant(user.id, await evaluateWeek(user.id), now)).points
    awarded += (await grant(user.id, await evaluateSeals(user.id), now)).points
  }

  // `awarded` rides along so the button can stamp what was just earned without a
  // second round trip. It is extra to `ProgressSnapshot`, which zod drops on the
  // way in, so the typed client is unaffected and only the caller that wants it
  // reads it.
  return json({ ...(await snapshotFor(user.id)), awarded })
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

/** CORS preflight, so the desktop app can send an Authorization header. */
export const OPTIONS = preflight
