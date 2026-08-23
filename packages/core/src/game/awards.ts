/**
 * What an event is worth, and the key that stops it being worth that twice.
 *
 * This is the only place XP arithmetic exists. Both apps and the API read it,
 * so nothing can quietly disagree about what a lesson pays.
 *
 * The weights are derived from the content rather than authored beside it:
 * `estimatedMinutes`, `timeboxMinutes` and a module's `difficulty` are already
 * in the manifest, and `docs/CURRICULUM.md` requires them to be measured rather
 * than estimated. So the economy cannot drift from the course, and adding a
 * course prices itself.
 */

export type AwardKind = 'lesson' | 'exercise' | 'module' | 'quest' | 'streak' | 'seal'

/**
 * Bumped when any weight below changes.
 *
 * Stored on every award so a total can be explained later, and so a client
 * showing an optimistic number can tell it was computed under older rules.
 */
export const RULES_VERSION = 1

export interface Award {
  kind: AwardKind
  /**
   * The idempotency key. A function of the user, the kind, and a natural key for
   * the thing rewarded, and never of a timestamp, an attempt number, or anything
   * else that changes between two identical actions.
   */
  awardKey: string
  points: number
  courseId?: string
}

const DIFFICULTY_MULTIPLIER: Record<string, number> = {
  beginner: 1,
  intermediate: 1.25,
  advanced: 1.5,
}

export function difficultyMultiplier(difficulty: string): number {
  return DIFFICULTY_MULTIPLIER[difficulty] ?? 1
}

/** The shapes this module needs, kept structural so it does not import content types. */
export interface LessonLike {
  id: string
  estimatedMinutes: number
}

export interface ModuleLike {
  id: string
  courseId: string
  difficulty: string
}

export interface ExerciseLike {
  id: string
  timeboxMinutes: number
}

/** One XP per measured minute of reading. Ranges from 12 to 60. */
export function lessonAward(lesson: LessonLike, module: ModuleLike): Award {
  return {
    kind: 'lesson',
    awardKey: `lesson:${lesson.id}`,
    points: Math.round(lesson.estimatedMinutes),
    courseId: module.courseId,
  }
}

export function moduleAward(module: ModuleLike): Award {
  return {
    kind: 'module',
    awardKey: `module:${module.id}`,
    points: Math.round(100 * difficultyMultiplier(module.difficulty)),
    courseId: module.courseId,
  }
}

export interface ExerciseContext {
  /** The learner revealed the reference for this exercise, ever. Sticky. */
  peeked: boolean
  /** Failed runs recorded for this exercise before the one being awarded. */
  priorFailures: number
}

const NO_PEEK_BONUS = 0.25
const FIRST_RUN_BONUS = 0.15

/**
 * A passing run, as up to three separately keyed awards.
 *
 * They are separate rather than one summed number so each pays at most once on
 * its own terms, and so a total can be read back and explained. The base is
 * `timeboxMinutes × 2 × difficulty`, which ranges from 20 to 120.
 *
 * Note what is not here: nothing pays for a failed run, and nothing pays for
 * time spent. Paying for time rewards leaving a tab open, and paying per run
 * rewards mashing the button.
 */
export function exerciseAwards(
  exercise: ExerciseLike,
  module: ModuleLike,
  context: ExerciseContext,
): Award[] {
  const base = Math.round(exercise.timeboxMinutes * 2 * difficultyMultiplier(module.difficulty))
  const subject = `${module.courseId}/${module.id}/${exercise.id}`

  const awards: Award[] = [
    {
      kind: 'exercise',
      awardKey: `exercise:pass:${subject}`,
      points: base,
      courseId: module.courseId,
    },
  ]

  if (!context.peeked) {
    awards.push({
      kind: 'exercise',
      awardKey: `exercise:nopeek:${subject}`,
      points: Math.round(base * NO_PEEK_BONUS),
      courseId: module.courseId,
    })
  }

  if (context.priorFailures === 0) {
    awards.push({
      kind: 'exercise',
      awardKey: `exercise:firstrun:${subject}`,
      points: Math.round(base * FIRST_RUN_BONUS),
      courseId: module.courseId,
    })
  }

  return awards
}

export const QUEST_POINTS = { daily: 40, weekly: 150 } as const

export function questAward(questId: string, serverDay: string, weekly: boolean): Award {
  return {
    kind: 'quest',
    // The day comes from the server, never the client, so moving a laptop clock
    // cannot mint a fresh key for a quest already claimed.
    awardKey: `quest:${questId}:${serverDay}`,
    points: weekly ? QUEST_POINTS.weekly : QUEST_POINTS.daily,
  }
}

const STREAK_STEP = 7
const STREAK_UNIT = 25
const STREAK_CAP = 200

/**
 * A milestone every seventh day, worth more the longer the run, capped so a
 * streak cannot become the cheapest XP in the game.
 */
export function streakAward(days: number): Award | null {
  if (days < STREAK_STEP || days % STREAK_STEP !== 0) return null
  return {
    kind: 'streak',
    awardKey: `streak:${days}`,
    points: Math.min(STREAK_CAP, STREAK_UNIT * (days / STREAK_STEP)),
  }
}

export function sealAward(sealId: string, points: number, courseId?: string): Award {
  return { kind: 'seal', awardKey: `seal:${sealId}`, points, courseId }
}
