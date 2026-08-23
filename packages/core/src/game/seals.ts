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
  streakDays: number
  freezesSpent: number
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
  {
    id: 'week',
    name: 'A week',
    requirement: 'Work seven days running',
    points: 40,
    earned: (e) => e.streakDays >= 7,
  },
  {
    id: 'month',
    name: 'A month',
    requirement: 'Work thirty days running',
    points: 120,
    earned: (e) => e.streakDays >= 30,
  },
  {
    id: 'hundred',
    name: 'A hundred',
    requirement: 'Work a hundred days running',
    points: 400,
    earned: (e) => e.streakDays >= 100,
  },
  {
    id: 'kept-the-chain',
    name: 'Kept the chain',
    requirement: 'Have a freeze save your streak',
    points: 30,
    earned: (e) => e.freezesSpent >= 1,
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
    streakDays: 0,
    freezesSpent: 0,
    catalogue: { exerciseIds: [], lessonIds: [] },
  }
}
