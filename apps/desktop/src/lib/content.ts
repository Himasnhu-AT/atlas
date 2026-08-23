import type { CourseEntry, LessonEntry, Manifest, ModuleEntry } from '@atlas/learning'
import manifest from '@atlas/learning/manifest'

/**
 * Every read of the course catalogue goes through here, so the surface this app
 * depends on from @atlas/learning stays narrow.
 *
 * The manifest is bundled, so the app opens and works with no network. A newer
 * copy can be fetched from the API later without changing anything below.
 */

const catalogue = manifest as unknown as Manifest

// A missing or malformed manifest used to throw here at import time, which
// unmounts everything and leaves a blank window with no clue why. Two ways it
// happens: `pnpm content` has not run, or Vite pre-bundled this package and
// mangled the JSON default export (see `optimizeDeps.exclude` in vite.config).
if (!catalogue || !Array.isArray(catalogue.courses)) {
  throw new Error(
    'The course manifest is missing or malformed. Run `pnpm content`, and check that ' +
      '@atlas/learning is listed in optimizeDeps.exclude in vite.config.ts.',
  )
}

export const courses: readonly CourseEntry[] = [...catalogue.courses]
  .filter((entry) => entry.isActive)
  .sort((a, b) => a.order - b.order)

export function modulesOf(course: CourseEntry): readonly ModuleEntry[] {
  return [...course.modules].filter((m) => m.isActive).sort((a, b) => a.order - b.order)
}

export const contentVersion = catalogue.contentVersion

export interface LessonRef {
  course: CourseEntry
  module: ModuleEntry
  lesson: LessonEntry
  /** Position in the flattened reading order across every course. */
  index: number
}

/**
 * Reading order across the whole catalogue, courses in catalogue order.
 *
 * `neighboursOf` walks this, so "next" does step from the last lesson of one
 * course into the first of the next. That is deliberate here and not on the web:
 * this app is a practice surface with one lesson open at a time, and stopping
 * dead at a course boundary would leave the Next button disabled with more work
 * available. The header always names the course, so nobody is moved silently.
 */
export const lessonSequence: readonly LessonRef[] = courses
  .flatMap((course) =>
    modulesOf(course).flatMap((module) =>
      [...module.lessons]
        .sort((a, b) => a.order - b.order)
        .map((lesson) => ({ course, module, lesson })),
    ),
  )
  .map((ref, index) => ({ ...ref, index }))

export const firstLessonRef: LessonRef | undefined = lessonSequence[0]

export const firstExerciseRef: LessonRef | undefined = lessonSequence.find(
  (ref) => ref.lesson.exercise !== undefined,
)

export const totalLessons = lessonSequence.length
export const totalExercises = lessonSequence.filter((ref) => ref.lesson.exercise).length

export function findCourseBySlug(slug: string | undefined): CourseEntry | undefined {
  if (!slug) return undefined
  return courses.find((course) => course.slug === slug)
}

export function findLessonRef(
  courseSlug: string | undefined,
  moduleSlug: string | undefined,
  lessonSlug: string | undefined,
): LessonRef | undefined {
  if (!courseSlug || !moduleSlug || !lessonSlug) return undefined
  return lessonSequence.find(
    (ref) =>
      ref.course.slug === courseSlug &&
      ref.module.slug === moduleSlug &&
      ref.lesson.slug === lessonSlug,
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

export function practicePath(ref: LessonRef): string {
  return `/practice/${ref.course.slug}/${ref.module.slug}/${ref.lesson.slug}`
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
  // Namespaced by course as well as module. Exercise ids are unique across the
  // catalogue by rule now, but the path says which course a directory belongs to
  // without having to look the id up, and a learner opening the sandbox should
  // see their work grouped the way the catalogue is.
  return `exercises/${ref.course.slug}/${ref.module.slug}/${exercise.id}`
}

/** The learner's working file. Fixed, because the test imports from it. */
export const SOLUTION_FILE = 'solution.py'

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours} hr` : `${hours} hr ${rest} min`
}
