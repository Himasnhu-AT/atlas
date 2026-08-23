import 'server-only'

import {
  type Award,
  EMPTY_COUNTS,
  type GameState,
  type QuestCounts,
  RULES_VERSION,
  type SealEvidence,
  SEALS,
  exerciseAwards,
  freezesEarned,
  isoWeekOf,
  lessonAward,
  levelProgress,
  moduleAward,
  newlyEarnedSeals,
  questForWeek,
  questProgress,
  questsForDay,
  romanFor,
  sealAward,
  streakAward,
  streakState,
} from '@atlas/core'

import { activeCourses, everyModule, exerciseIndex } from '@/lib/content'
import { store, type StoredAward } from './store'

/**
 * Granting XP, server-side, and assembling the state both apps render.
 *
 * The rule this file exists to enforce: **the client never asks for XP.** No
 * request body carries a point value, an award key or an award kind. Every
 * award is recomputed here from events the API already records, and written
 * under a key that makes a replay free. A handler that accepted a number from a
 * client would make the leaderboard a curl exercise.
 *
 * The other rule: **the server owns the calendar.** A client's `occurredAt` is
 * evidence and is clamped; the day a piece of activity belongs to is decided
 * here. That is what stops moving a laptop clock backwards from farming daily
 * quests.
 */

/** How far back a client timestamp may claim to be. Matches the token lifetime. */
const MAX_BACKDATE_MS = 30 * 24 * 60 * 60 * 1000

/**
 * A client timestamp, made safe.
 *
 * Never in the future, and never more than a month old. An offline device that
 * has been away longer than its token lives has to pair again anyway.
 */
export function clampOccurredAt(claimed: string | undefined, now = new Date()): string {
  if (!claimed) return now.toISOString()
  const at = Date.parse(claimed)
  if (Number.isNaN(at)) return now.toISOString()
  return new Date(Math.min(Math.max(at, now.getTime() - MAX_BACKDATE_MS), now.getTime())).toISOString()
}

/** The day the server says it is, for a user. */
export function serverDay(now = new Date()): string {
  return now.toISOString().slice(0, 10)
}

function toStored(award: Award, occurredAt: string): StoredAward {
  const at = new Date().toISOString()
  return {
    awardKey: award.awardKey,
    kind: award.kind,
    points: award.points,
    courseId: award.courseId,
    rulesVersion: RULES_VERSION,
    occurredAt,
    awardedAt: at,
  }
}

/** Writes a batch and reports what was actually new. */
export async function grant(
  userId: string,
  awards: Award[],
  occurredAt: string,
): Promise<{ granted: Award[]; points: number }> {
  const granted: Award[] = []
  let points = 0

  for (const award of awards) {
    const paid = await store().awardXp(userId, toStored(award, occurredAt))
    if (paid > 0) {
      granted.push(award)
      points += paid
    }
  }

  return { granted, points }
}

/** Awards for finishing a lesson, plus its module if that finished it too. */
export async function awardsForLessonCompletion(
  userId: string,
  lessonId: string,
  moduleId: string,
): Promise<Award[]> {
  const module = everyModule().find((m) => m.id === moduleId)
  const lesson = module?.lessons.find((l) => l.id === lessonId)
  if (!module || !lesson) return []

  const awards: Award[] = [lessonAward(lesson, module)]

  const snapshot = await store().progressFor(userId)
  const done = new Set(
    snapshot.lessons.filter((r) => r.status === 'completed').map((r) => r.lessonId),
  )
  if (module.lessons.length > 0 && module.lessons.every((l) => done.has(l.id))) {
    awards.push(moduleAward(module))
  }

  return awards
}

/** Awards for a passing run. Returns nothing for a failure, deliberately. */
export async function awardsForAttempt(
  userId: string,
  exerciseId: string,
  passed: boolean,
): Promise<Award[]> {
  if (!passed) return []

  const located = exerciseIndex().get(exerciseId)
  if (!located) return []

  const module = everyModule().find((m) => m.id === located.moduleId)
  const lesson = module?.lessons.find((l) => l.id === located.lessonId)
  if (!module || !lesson?.exercise) return []

  const state = await store().exerciseState(userId, exerciseId)
  const stats = (await store().exerciseStats(userId)).find((s) => s.exerciseId === exerciseId)

  return exerciseAwards(lesson.exercise, module, {
    peeked: Boolean(state?.peekedReferenceAt),
    // The run being awarded has already been recorded by the time this is
    // called, so its own failure must not count against its own first-run bonus.
    priorFailures: stats?.failuresBeforePass ?? 0,
  })
}

/** Everything the seal predicates read, assembled once. */
export async function sealEvidence(userId: string): Promise<SealEvidence> {
  const [snapshot, stats, game] = await Promise.all([
    store().progressFor(userId),
    store().exerciseStats(userId),
    store().gameFor(userId),
  ])

  const modules = everyModule()
  const byId = new Map(modules.map((m) => [m.id, m]))

  const passedExercises = new Set(stats.filter((s) => s.passes > 0).map((s) => s.exerciseId))
  const failuresBeforePass = new Map(stats.map((s) => [s.exerciseId, s.failuresBeforePass]))

  const index = exerciseIndex()
  const passedInsideTimebox = new Set<string>()
  const peekedExercises = new Set<string>()
  for (const stat of stats) {
    const located = index.get(stat.exerciseId)
    const module = located && byId.get(located.moduleId)
    const lesson = module?.lessons.find((l) => l.id === located!.lessonId)
    const timebox = lesson?.exercise?.timeboxMinutes
    if (
      stat.passes > 0 &&
      timebox !== undefined &&
      stat.bestPassDurationMs !== undefined &&
      stat.bestPassDurationMs <= timebox * 60_000
    ) {
      passedInsideTimebox.add(stat.exerciseId)
    }

    const state = await store().exerciseState(userId, stat.exerciseId)
    if (state?.peekedReferenceAt) peekedExercises.add(stat.exerciseId)
  }

  const completedModules = new Set(
    snapshot.modules.filter((m) => m.status === 'completed').map((m) => m.moduleId),
  )
  const completedLessons = new Set(
    snapshot.lessons.filter((l) => l.status === 'completed').map((l) => l.lessonId),
  )

  const coursesTouched = new Set<string>()
  for (const id of completedModules) {
    const module = byId.get(id)
    if (module) coursesTouched.add(module.courseId)
  }

  const coursesCompleted = new Set<string>()
  for (const course of activeCourses()) {
    const ids = course.modules.map((m) => m.id)
    if (ids.length > 0 && ids.every((id) => completedModules.has(id))) {
      coursesCompleted.add(course.id)
    }
  }

  const streak = streakState(
    snapshot.activity,
    serverDay(),
    freezesEarned(snapshot.activity),
  )

  return {
    passedExercises,
    peekedExercises,
    failuresBeforePass,
    passedInsideTimebox,
    completedModules,
    completedLessons,
    coursesTouched,
    coursesCompleted,
    streakDays: Math.max(streak.days, game.longestStreak),
    freezesSpent: streak.freezesSpent,
    catalogue: {
      exerciseIds: [...index.keys()],
      lessonIds: modules.flatMap((m) => m.lessons.map((l) => l.id)),
    },
  }
}

/**
 * Re-evaluate every seal and grant what is newly earned.
 *
 * Predicates are pure over evidence rather than hooked to a live event, so this
 * catches up anything a learner already qualified for, including a seal added
 * after they earned it.
 */
export async function evaluateSeals(userId: string): Promise<Award[]> {
  const [evidence, held] = await Promise.all([sealEvidence(userId), store().sealsFor(userId)])
  const alreadyEarned = new Set(held.map((s) => s.sealId))
  const earned = newlyEarnedSeals(evidence, alreadyEarned)

  const awards: Award[] = []
  for (const seal of earned) {
    if (await store().grantSeal(userId, seal.id)) {
      awards.push(sealAward(seal.id, seal.points))
    }
  }
  return awards
}

/** Streak milestone, if today's streak just crossed one. */
export async function evaluateStreak(userId: string): Promise<Award[]> {
  const snapshot = await store().progressFor(userId)
  const streak = streakState(snapshot.activity, serverDay(), freezesEarned(snapshot.activity))

  const game = await store().gameFor(userId)
  if (streak.days > game.longestStreak) {
    await store().updateGame(userId, { longestStreak: streak.days })
  }

  const award = streakAward(streak.days)
  return award ? [award] : []
}

/**
 * Quest counts over a window.
 *
 * Derived from rows the API already writes, so quests need no table of their
 * own: nothing is stored until one is claimed, and a claim is just a ledger row.
 */
async function countsSince(userId: string, since: string): Promise<QuestCounts> {
  const [snapshot, stats] = await Promise.all([
    store().progressFor(userId),
    store().exerciseStats(userId),
  ])

  const counts: QuestCounts = { ...EMPTY_COUNTS }

  counts.lessons_completed = snapshot.lessons.filter(
    (l) => l.status === 'completed' && (l.completedAt ?? '') >= since,
  ).length

  counts.modules_completed = snapshot.modules.filter(
    (m) => m.status === 'completed' && (m.completedAt ?? '') >= since,
  ).length

  counts.active_days = snapshot.activity.filter(
    (d) => d.day >= since.slice(0, 10) && (d.lessonsTouched > 0 || d.attempts > 0),
  ).length

  const index = exerciseIndex()
  const byId = new Map(everyModule().map((m) => [m.id, m]))

  for (const stat of stats) {
    if (stat.passes === 0 || (stat.firstPassedAt ?? '') < since) continue
    counts.exercises_passed += 1

    if (stat.failuresBeforePass === 0) counts.exercises_passed_first_run += 1

    const located = index.get(stat.exerciseId)
    if (!located || !byId.has(located.moduleId)) continue
    const state = await store().exerciseState(userId, stat.exerciseId)
    if (!state?.peekedReferenceAt) counts.exercises_passed_unaided += 1
  }

  return counts
}

/** Start of the ISO week containing a day, as an ISO timestamp. */
function startOfIsoWeek(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  const weekday = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() - (weekday - 1))
  return date.toISOString()
}

export function weekStart(day = serverDay()): string {
  return startOfIsoWeek(day)
}

/**
 * The whole game state, in one read, the way `/api/progress` returns one
 * snapshot. Every number is derived here; none of it is ever sent up.
 */
export async function gameStateFor(userId: string): Promise<GameState> {
  const day = serverDay()
  const isoWeek = isoWeekOf(day)

  const [snapshot, game, heldSeals, awards, stats] = await Promise.all([
    store().progressFor(userId),
    store().gameFor(userId),
    store().sealsFor(userId),
    store().awardsFor(userId),
    store().exerciseStats(userId),
  ])

  const level = levelProgress(game.totalXp)
  const streak = streakState(snapshot.activity, day, freezesEarned(snapshot.activity))

  const claimed = new Set(awards.map((a) => a.awardKey))
  const [dailyCounts, weeklyCounts] = await Promise.all([
    countsSince(userId, `${day}T00:00:00.000Z`),
    countsSince(userId, weekStart(day)),
  ])

  const daily = questsForDay(userId, day).map((quest) => {
    const progress = questProgress(quest, dailyCounts)
    return {
      id: quest.id,
      period: quest.period,
      title: quest.title,
      target: quest.target,
      progress: progress.progress,
      complete: progress.complete,
      claimed: claimed.has(`quest:${quest.id}:${day}`),
      points: 40,
      claimKey: `quest:${quest.id}:${day}`,
    }
  })

  const weekly = questForWeek(userId, isoWeek)
  const weeklyProgress = questProgress(weekly, weeklyCounts)
  const quests = [
    ...daily,
    {
      id: weekly.id,
      period: weekly.period,
      title: weekly.title,
      target: weekly.target,
      progress: weeklyProgress.progress,
      complete: weeklyProgress.complete,
      claimed: claimed.has(`quest:${weekly.id}:${isoWeek}`),
      points: 150,
      claimKey: `quest:${weekly.id}:${isoWeek}`,
    },
  ]

  const earnedAt = new Map(heldSeals.map((s) => [s.sealId, s.earnedAt]))
  // Every seal, earned or not, so the ledger can show the blanks. A locked seal
  // a learner can see is a goal; one they cannot is a surprise.
  const seals = SEALS.map((seal) => ({
    id: seal.id,
    name: seal.name,
    requirement: seal.requirement,
    points: seal.points,
    earnedAt: earnedAt.get(seal.id),
  }))

  const completedLessons = new Set(
    snapshot.lessons.filter((l) => l.status === 'completed').map((l) => l.lessonId),
  )
  const completedModules = new Set(
    snapshot.modules.filter((m) => m.status === 'completed').map((m) => m.moduleId),
  )
  const passed = new Set(stats.filter((s) => s.passes > 0).map((s) => s.exerciseId))
  const xpByCourse = new Map<string, number>()
  for (const award of awards) {
    if (!award.courseId) continue
    xpByCourse.set(award.courseId, (xpByCourse.get(award.courseId) ?? 0) + award.points)
  }

  const courses = activeCourses().map((course) => {
    const modules = course.modules
    const lessons = modules.flatMap((m) => m.lessons)
    const exercises = lessons.flatMap((l) => (l.exercise ? [l.exercise.id] : []))
    return {
      courseId: course.id,
      xp: xpByCourse.get(course.id) ?? 0,
      lessonsCompleted: lessons.filter((l) => completedLessons.has(l.id)).length,
      lessonsTotal: lessons.length,
      exercisesPassed: exercises.filter((id) => passed.has(id)).length,
      exercisesTotal: exercises.length,
      modulesCompleted: modules.filter((m) => completedModules.has(m.id)).length,
      modulesTotal: modules.length,
    }
  })

  return {
    level: {
      level: level.level,
      totalXp: level.totalXp,
      intoLevel: level.intoLevel,
      levelSpan: level.levelSpan,
      toNextLevel: level.toNextLevel,
      nextLevelAt: level.nextLevelAt,
      rank: {
        tier: level.rank.tier,
        name: level.rank.name,
        roman: romanFor(level.rank.tier),
      },
    },
    streak: {
      days: streak.days,
      rawDays: streak.rawDays,
      freezesAvailable: streak.freezesAvailable,
      freezesSpent: streak.freezesSpent,
      longest: Math.max(game.longestStreak, streak.days),
    },
    quests,
    seals,
    courses,
    leaderboardOptIn: game.leaderboardOptIn,
    rulesVersion: RULES_VERSION,
  }
}

/**
 * Claim a quest.
 *
 * The claim key names a quest and a day, and the server re-derives whether that
 * quest was actually offered and actually completed before paying. A client
 * that invents a key gets nothing, and the award key makes a replay free.
 */
export async function claimQuest(userId: string, claimKey: string): Promise<number> {
  const state = await gameStateFor(userId)
  const quest = state.quests.find((q) => q.claimKey === claimKey)
  if (!quest || !quest.complete || quest.claimed) return 0

  const { points } = await grant(
    userId,
    [{ kind: 'quest', awardKey: quest.claimKey, points: quest.points }],
    new Date().toISOString(),
  )
  return points
}
