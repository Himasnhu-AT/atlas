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

export type AwardKind = 'lesson' | 'exercise' | 'module' | 'quest' | 'week' | 'seal'

/**
 * Bumped when any weight below changes.
 *
 * Stored on every award so a total can be explained later, and so a client
 * showing an optimistic number can tell it was computed under older rules.
 */
export const RULES_VERSION = 2

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

/**
 * A flat, small acknowledgement that a lesson was read.
 *
 * Deliberately not one XP per measured minute, which is where this started.
 * "Mark complete" is self-reported and takes one click, so paying by length made
 * a sixty-minute lesson worth sixty XP to anyone willing to click through it,
 * and put a third of the whole economy behind a button that verifies nothing.
 * Every platform that shipped a farmable currency has since removed it or
 * stopped paying for reading altogether.
 *
 * Flat and small keeps the acknowledgement, keeps the ten lessons that carry no
 * exercise worth something, and moves the weight to work that is actually
 * checked: exercises are graded, and they are now about 85% of the economy.
 */
export const LESSON_POINTS = 5

export function lessonAward(lesson: LessonLike, module: ModuleLike): Award {
  return {
    kind: 'lesson',
    awardKey: `lesson:${lesson.id}`,
    points: LESSON_POINTS,
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

export const WEEK_MET_POINTS = 60

/**
 * Meeting the week's self-set target, paid once for that week.
 *
 * Keyed by the week rather than by a running count, so it pays for the week that
 * was actually worked and there is nothing to lose by missing the next one.
 */
export function weekMetAward(weekStart: string): Award {
  return {
    kind: 'week',
    awardKey: `week:${weekStart}`,
    points: WEEK_MET_POINTS,
  }
}

const WEEK_MILESTONES = [4, 12, 26, 52] as const

/**
 * A milestone for a run of met weeks.
 *
 * Sparse on purpose. These mark a habit that genuinely formed rather than
 * metering out a reward often enough to make missing one feel like a loss.
 */
export function weekMilestoneAward(weeksInARow: number): Award | null {
  if (!WEEK_MILESTONES.includes(weeksInARow as (typeof WEEK_MILESTONES)[number])) return null
  return {
    kind: 'week',
    awardKey: `weeks:${weeksInARow}`,
    points: 50 * (WEEK_MILESTONES.indexOf(weeksInARow as (typeof WEEK_MILESTONES)[number]) + 1),
  }
}

export function sealAward(sealId: string, points: number, courseId?: string): Award {
  return { kind: 'seal', awardKey: `seal:${sealId}`, points, courseId }
}
