import type { LessonEntry, Manifest, ModuleEntry } from '@learn/learning'
import manifest from '@learn/learning/manifest'

/**
 * Every read of the course catalogue goes through here, so the surface this app
 * depends on from @learn/learning stays narrow.
 *
 * The manifest is bundled, so the app opens and works with no network. A newer
 * copy can be fetched from the API later without changing anything below.
 */

const course = manifest as Manifest

// A missing or malformed manifest used to throw here at import time, which
// unmounts everything and leaves a blank window with no clue why. Two ways it
// happens: `pnpm content` has not run, or Vite pre-bundled this package and
// mangled the JSON default export (see `optimizeDeps.exclude` in vite.config).
if (!course || !Array.isArray(course.modules)) {
  throw new Error(
    'The course manifest is missing or malformed. Run `pnpm content`, and check that ' +
      '@learn/learning is listed in optimizeDeps.exclude in vite.config.ts.',
  )
}

export const courseModules: readonly ModuleEntry[] = [...course.modules]
  .filter((module) => module.isActive)
  .sort((a, b) => a.order - b.order)

export const contentVersion = course.contentVersion

export interface LessonRef {
  module: ModuleEntry
  lesson: LessonEntry
  /** Position in the flattened, course-wide reading order. */
  index: number
}

export const lessonSequence: readonly LessonRef[] = courseModules
  .flatMap((module) =>
    [...module.lessons]
      .sort((a, b) => a.order - b.order)
      .map((lesson) => ({ module, lesson })),
  )
  .map((ref, index) => ({ ...ref, index }))

export const firstLessonRef: LessonRef | undefined = lessonSequence[0]

export const firstExerciseRef: LessonRef | undefined = lessonSequence.find(
  (ref) => ref.lesson.exercise !== undefined,
)

export const totalLessons = lessonSequence.length
export const totalExercises = lessonSequence.filter((ref) => ref.lesson.exercise).length

export function getModuleBySlug(slug: string | undefined): ModuleEntry | undefined {
  if (!slug) return undefined
  return courseModules.find((module) => module.slug === slug)
}

export function findLessonRef(
  moduleSlug: string | undefined,
  lessonSlug: string | undefined,
): LessonRef | undefined {
  if (!moduleSlug || !lessonSlug) return undefined
  return lessonSequence.find(
    (ref) => ref.module.slug === moduleSlug && ref.lesson.slug === lessonSlug,
  )
}

export function findLessonRefById(lessonId: string): LessonRef | undefined {
  return lessonSequence.find((ref) => ref.lesson.id === lessonId)
}

export interface LessonNeighbours {
  previous?: LessonRef
  next?: LessonRef
}

export function neighboursOf(ref: LessonRef): LessonNeighbours {
  return {
    previous: lessonSequence[ref.index - 1],
    next: lessonSequence[ref.index + 1],
  }
}

export function practicePath(moduleSlug: string, lessonSlug: string): string {
  return `/practice/${moduleSlug}/${lessonSlug}`
}

/**
 * The exercise's directory inside the sandboxed workspace.
 *
 * Every file the exercise needs lives here: the learner's `solution.py`, the
 * test, the reference, and the mock client. Keeping them in one directory is
 * what lets `python3 test.py` work with no path juggling, exactly as it would
 * in a normal project.
 */
export function exerciseDir(ref: LessonRef): string | undefined {
  const { exercise } = ref.lesson
  if (!exercise) return undefined
  return `exercises/${ref.module.slug}/${exercise.id}`
}

/** The learner's working file. Fixed, because the test imports from it. */
export const SOLUTION_FILE = 'solution.py'

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`
}
