/**
 * Seals: the wax stamps a learner collects.
 *
 * Each is a real feat rather than a participation marker, and each is a pure
 * predicate over one evidence shape. That matters for two reasons. A seal whose
 * condition cannot be computed from data the platform actually records will
 * silently never fire, and nobody notices a reward that does not arrive. And
 * because they are pure, the whole set can be re-evaluated over history rather
 * than only caught live, so a seal added next month is awarded to the people who
 * already earned it.
 */

export interface SealEvidence {
  /** Exercise ids passed at least once. */
  passedExercises: ReadonlySet<string>
  /** Exercise ids whose reference was revealed. Sticky. */
  peekedExercises: ReadonlySet<string>
  /** Failed runs before the first pass, by exercise id. */
  failuresBeforePass: ReadonlyMap<string, number>
  /** Exercise ids passed inside their timebox. */
  passedInsideTimebox: ReadonlySet<string>
  /** Completed module ids. */
  completedModules: ReadonlySet<string>
  /** Completed lesson ids. */
  completedLessons: ReadonlySet<string>
  /** Course ids with at least one module completed. */
  coursesTouched: ReadonlySet<string>
  /** Course ids completed end to end. */
  coursesCompleted: ReadonlySet<string>
  /** Consecutive weeks the learner met their own target. */
  weeksInARow: number
  /** Weeks the target was met, ever. */
  weeksMet: number
  /** The catalogue, so "all of them" seals know what all means. */
  catalogue: {
    exerciseIds: readonly string[]
    lessonIds: readonly string[]
  }
}

export interface Seal {
  id: string
  name: string
  /** What the learner is told they have to do. */
  requirement: string
  points: number
  earned: (evidence: SealEvidence) => boolean
}

export const SEALS: readonly Seal[] = [
  {
    id: 'first-light',
    name: 'First light',
    requirement: 'Pass your first exercise',
    points: 25,
    earned: (e) => e.passedExercises.size >= 1,
  },
  {
    id: 'clean-run',
    name: 'Clean run',
    requirement: 'Pass an exercise with no failed run before it',
    points: 40,
    earned: (e) =>
      [...e.passedExercises].some((id) => (e.failuresBeforePass.get(id) ?? 0) === 0),
  },
  {
    id: 'stubborn',
    name: 'Stubborn',
    requirement: 'Pass an exercise after ten failed runs',
    points: 60,
    // Deliberately rewards the long fight rather than the quick win. Both are in
    // the set, because a game that only pays the naturally fast is telling
    // everyone else the wrong thing about learning.
    earned: (e) => [...e.failuresBeforePass.values()].some((n) => n >= 10),
  },
  {
    id: 'inside-the-box',
    name: 'Inside the box',
    requirement: 'Pass an exercise inside its timebox',
    points: 40,
    earned: (e) => e.passedInsideTimebox.size >= 1,
  },
  {
    id: 'ten-green',
    name: 'Ten green',
    requirement: 'Pass ten exercises',
    points: 80,
    earned: (e) => e.passedExercises.size >= 10,
  },
  {
    id: 'unaided-module',
    name: 'Unaided',
    requirement: 'Finish a module without revealing a single reference',
    points: 100,
    earned: (e) =>
      e.completedModules.size >= 1 &&
      [...e.passedExercises].every((id) => !e.peekedExercises.has(id)) &&
      e.passedExercises.size >= 1,
  },
  {
    id: 'every-green',
    name: 'Every green',
    requirement: 'Pass every exercise in the catalogue',
    points: 250,
    earned: (e) =>
      e.catalogue.exerciseIds.length > 0 &&
      e.catalogue.exerciseIds.every((id) => e.passedExercises.has(id)),
  },
  {
    id: 'read-it-all',
    name: 'Read it all',
    requirement: 'Finish every lesson in the catalogue',
    points: 250,
    earned: (e) =>
      e.catalogue.lessonIds.length > 0 &&
      e.catalogue.lessonIds.every((id) => e.completedLessons.has(id)),
  },
  {
    id: 'course-cleared',
    name: 'Course cleared',
    requirement: 'Finish a course end to end',
    points: 200,
    earned: (e) => e.coursesCompleted.size >= 1,
  },
  {
    id: 'polymath',
    name: 'Polymath',
    requirement: 'Clear a module in two different courses',
    points: 120,
    // The one seal that only exists because the platform holds more than one
    // course, and the one that says out loud that breadth is welcome here.
    earned: (e) => e.coursesTouched.size >= 2,
  },
  // Weeks, not days. These used to be seven, thirty and a hundred consecutive
  // days, which asks a learner never to take two days off in three months.
  {
    id: 'first-week',
    name: 'First week',
    requirement: 'Meet your weekly target once',
    points: 30,
    earned: (e) => e.weeksMet >= 1,
  },
  {
    id: 'four-weeks',
    name: 'Four weeks',
    requirement: 'Meet your weekly target four weeks running',
    points: 90,
    earned: (e) => e.weeksInARow >= 4,
  },
  {
    id: 'a-season',
    name: 'A season',
    requirement: 'Meet your weekly target twelve weeks running',
    points: 200,
    earned: (e) => e.weeksInARow >= 12,
  },
  {
    id: 'a-year',
    name: 'A year',
    requirement: 'Meet your weekly target fifty-two weeks running',
    points: 500,
    earned: (e) => e.weeksInARow >= 52,
  },
]

export const SEALS_BY_ID: ReadonlyMap<string, Seal> = new Map(SEALS.map((s) => [s.id, s]))

/** Seals the evidence supports that have not been granted yet. */
export function newlyEarnedSeals(
  evidence: SealEvidence,
  alreadyEarned: ReadonlySet<string>,
): Seal[] {
  return SEALS.filter((seal) => !alreadyEarned.has(seal.id) && seal.earned(evidence))
}

export function emptyEvidence(): SealEvidence {
  return {
    passedExercises: new Set(),
    peekedExercises: new Set(),
    failuresBeforePass: new Map(),
    passedInsideTimebox: new Set(),
    completedModules: new Set(),
    completedLessons: new Set(),
    coursesTouched: new Set(),
    coursesCompleted: new Set(),
    weeksInARow: 0,
    weeksMet: 0,
    catalogue: { exerciseIds: [], lessonIds: [] },
  }
}
