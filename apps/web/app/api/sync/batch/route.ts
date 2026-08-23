import { z } from 'zod'
import { NewAttempt, UpdateLessonProgress } from '@atlas/core'

import { everyModule, exerciseIndex } from '@/lib/content'
import { json, parseBody, preflight, route } from '@/lib/server/respond'
import { currentDeviceId, requireUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import {
  awardsForAttempt,
  awardsForLessonCompletion,
  clampOccurredAt,
  evaluateSeals,
  evaluateWeek,
  gameStateFor,
  grant,
  serverDay,
} from '@/lib/server/xp'

/**
 * Draining a desktop outbox.
 *
 * The events are the request bodies of `/api/progress` and `/api/attempts`,
 * which is the point: the outbox is those two calls made durable and ordered,
 * not a second wire format that has to be kept in step with them.
 *
 * Two hundred sequential round trips on a bad connection is minutes, so a
 * backlog arrives in one request. The response is the authoritative snapshot
 * rather than a 204, which is also what keeps two paired machines agreeing
 * without either of them polling.
 */

const MAX_EVENTS = 200

const SyncEvent = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('lesson.progress'),
    clientEventId: z.string().min(1).max(64),
    occurredAt: z.iso.datetime().optional(),
    payload: UpdateLessonProgress,
  }),
  z.object({
    kind: z.literal('attempt.recorded'),
    clientEventId: z.string().min(1).max(64),
    occurredAt: z.iso.datetime().optional(),
    payload: NewAttempt,
  }),
])

const SyncBatch = z.object({ events: z.array(SyncEvent).max(MAX_EVENTS) })

export const POST = route(async (request) => {
  const user = await requireUser(request)
  const deviceId = await currentDeviceId(request)
  const body = await parseBody(request, SyncBatch)

  const modules = everyModule()
  const exercises = exerciseIndex()
  const day = serverDay()

  let awarded = 0
  let accepted = 0
  const rejected: { clientEventId: string; reason: string }[] = []

  // Strictly in the order the device queued them. A completion followed by an
  // un-completion, replayed the other way round, leaves the lesson in the wrong
  // state.
  for (const event of body.events) {
    const occurredAt = clampOccurredAt(event.occurredAt)

    if (event.kind === 'lesson.progress') {
      const module = modules.find((m) => m.id === event.payload.moduleId)
      const lesson = module?.lessons.find((l) => l.id === event.payload.lessonId)
      if (!module || !lesson) {
        rejected.push({ clientEventId: event.clientEventId, reason: 'unknown lesson' })
        continue
      }

      const existing = (await store().progressFor(user.id)).lessons.find(
        (row) => row.lessonId === event.payload.lessonId,
      )
      const now = new Date().toISOString()

      await store().upsertLessonProgress(user.id, {
        lessonId: event.payload.lessonId,
        moduleId: event.payload.moduleId,
        status: event.payload.status,
        secondsSpent: (existing?.secondsSpent ?? 0) + (event.payload.secondsSpent ?? 0),
        startedAt: existing?.startedAt ?? occurredAt,
        completedAt:
          event.payload.status === 'completed' ? (existing?.completedAt ?? now) : undefined,
      })
      // Offline work counts toward the day it happened, which is generous and
      // fair to someone who worked on a plane. Quests and the weekly target use
      // the server's day, so neither can be farmed by moving a clock.
      await store().recordActivity(user.id, occurredAt.slice(0, 10), 'lesson')
      await recomputeModule(user.id, event.payload.moduleId)

      if (event.payload.status === 'completed') {
        const awards = await awardsForLessonCompletion(
          user.id,
          event.payload.lessonId,
          event.payload.moduleId,
        )
        awarded += (await grant(user.id, awards, occurredAt)).points
      }
      accepted += 1
      continue
    }

    if (!exercises.has(event.payload.exerciseId)) {
      rejected.push({ clientEventId: event.clientEventId, reason: 'unknown exercise' })
      continue
    }

    const applied = await store().recordAttempt(
      user.id,
      { ...event.payload, stdoutTail: event.payload.stdoutTail?.slice(-4000) },
      event.clientEventId,
    )

    // A batch this device already sent. Award keys would have stopped it paying
    // twice, but not being counted twice, and the counters are what the
    // first-run bonus and two seals read: five replays of two genuine failures
    // is enough to mint Stubborn. Still accepted, because it was accepted once
    // and the device only needs to know it can drop it.
    if (!applied) {
      accepted += 1
      continue
    }

    await store().recordActivity(user.id, occurredAt.slice(0, 10), 'attempt')

    const awards = await awardsForAttempt(user.id, event.payload.exerciseId, event.payload.passed)
    awarded += (await grant(user.id, awards, occurredAt)).points
    accepted += 1
  }

  // Once for the batch, not once per event. A month of backlog draining would
  // otherwise fire forty separate awards and, on the client, forty toasts.
  const now = new Date().toISOString()
  awarded += (await grant(user.id, await evaluateWeek(user.id), now)).points
  awarded += (await grant(user.id, await evaluateSeals(user.id), now)).points

  void day
  void deviceId

  return json({
    accepted,
    rejected,
    awarded,
    game: await gameStateFor(user.id),
  })
})

/** Same rollup the single-event route does. Derived, so it cannot drift. */
async function recomputeModule(userId: string, moduleId: string): Promise<void> {
  const module = everyModule().find((m) => m.id === moduleId)
  if (!module) return

  const snapshot = await store().progressFor(userId)
  const lessonIds = new Set(module.lessons.map((lesson) => lesson.id))
  const rows = snapshot.lessons.filter((row) => lessonIds.has(row.lessonId))
  const completed = rows.filter((row) => row.status === 'completed').length
  const finished = completed === module.lessons.length && module.lessons.length > 0

  const now = new Date().toISOString()
  const previous = snapshot.modules.find((row) => row.moduleId === moduleId)

  await store().upsertModuleProgress(userId, {
    moduleId,
    status: finished ? 'completed' : rows.length > 0 ? 'in_progress' : 'available',
    lessonsCompleted: completed,
    lessonsTotal: module.lessons.length,
    startedAt: previous?.startedAt ?? now,
    completedAt: finished ? (previous?.completedAt ?? now) : undefined,
  })
}

export const OPTIONS = preflight
