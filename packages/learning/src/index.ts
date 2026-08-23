/**
 * Navigation over a built content manifest.
 *
 * These are pure functions taking a manifest rather than reading `dist/`
 * themselves. The web app imports the manifest at build time and the desktop app
 * loads a bundled or freshly synced copy, so neither can share a single import
 * of it. Keeping the functions pure also makes them testable without a build.
 *
 * The manifest holds courses, and a course holds modules. Most callers want one
 * course at a time, so the course-scoped functions take a `CourseEntry`. The few
 * that genuinely span the catalogue (search, the world map, a global lesson
 * count) say so in their names.
 */

import type { CourseEntry, LessonEntry, Manifest, ModuleEntry, TrackMeta } from './schema'

export * from './schema'

/** Courses a student can see, in display order. */
export function activeCourses(manifest: Manifest): CourseEntry[] {
  return manifest.courses.filter((c) => c.isActive).sort((a, b) => a.order - b.order)
}

export function getCourse(manifest: Manifest, slug: string): CourseEntry | undefined {
  return activeCourses(manifest).find((c) => c.slug === slug)
}

export function getCourseById(manifest: Manifest, id: string): CourseEntry | undefined {
  return activeCourses(manifest).find((c) => c.id === id)
}

/** Modules a student can see in one course, in display order. */
export function activeModules(course: CourseEntry): ModuleEntry[] {
  return course.modules.filter((m) => m.isActive).sort((a, b) => a.order - b.order)
}

/** Every visible module in the catalogue, course order then module order. */
export function allActiveModules(manifest: Manifest): ModuleEntry[] {
  return activeCourses(manifest).flatMap(activeModules)
}

export function modulesInTrack(course: CourseEntry, track: string): ModuleEntry[] {
  return activeModules(course).filter((m) => m.track === track)
}

/** The track record a module names, so a caller can render its label. */
export function trackOf(course: CourseEntry, module: ModuleEntry): TrackMeta | undefined {
  return course.tracks.find((t) => t.id === module.track)
}

export function getModule(course: CourseEntry, slug: string): ModuleEntry | undefined {
  return activeModules(course).find((m) => m.slug === slug)
}

export function getModuleById(manifest: Manifest, id: string): ModuleEntry | undefined {
  return allActiveModules(manifest).find((m) => m.id === id)
}

/** The course a module belongs to, by module id. */
export function courseOfModule(manifest: Manifest, moduleId: string): CourseEntry | undefined {
  return activeCourses(manifest).find((c) => c.modules.some((m) => m.id === moduleId))
}

export function getLesson(
  course: CourseEntry,
  moduleSlug: string,
  lessonSlug: string,
): { module: ModuleEntry; lesson: LessonEntry } | undefined {
  const module = getModule(course, moduleSlug)
  const lesson = module?.lessons.find((l) => l.slug === lessonSlug)
  return module && lesson ? { module, lesson } : undefined
}

/** Find a lesson anywhere in the catalogue, for deep links and resume. */
export function findLessonById(
  manifest: Manifest,
  lessonId: string,
): { course: CourseEntry; module: ModuleEntry; lesson: LessonEntry } | undefined {
  for (const course of activeCourses(manifest)) {
    for (const module of activeModules(course)) {
      const lesson = module.lessons.find((l) => l.id === lessonId)
      if (lesson) return { course, module, lesson }
    }
  }
  return undefined
}

/**
 * Every lesson in one course in reading order. This is the spine of prev/next
 * navigation and of `generateStaticParams` on the web.
 *
 * Deliberately course-scoped: "next lesson" must not walk off the end of a
 * course into an unrelated one.
 */
export function lessonSequence(course: CourseEntry): { module: ModuleEntry; lesson: LessonEntry }[] {
  return activeModules(course).flatMap((module) =>
    [...module.lessons].sort((a, b) => a.order - b.order).map((lesson) => ({ module, lesson })),
  )
}

export function neighbours(course: CourseEntry, lessonId: string) {
  const sequence = lessonSequence(course)
  const index = sequence.findIndex((entry) => entry.lesson.id === lessonId)
  if (index === -1) return { previous: undefined, next: undefined }
  return { previous: sequence[index - 1], next: sequence[index + 1] }
}

/**
 * Whether a module's prerequisites are all complete.
 *
 * The server decides what a student may open. This mirrors that rule on the
 * client so the UI can grey a module out without a round trip, and it is not a
 * substitute for the server's check.
 */
export function isUnlocked(module: ModuleEntry, completedModuleIds: Iterable<string>): boolean {
  const done = new Set(completedModuleIds)
  return module.prerequisites.every((id) => done.has(id))
}

export function lessonCount(course: CourseEntry): number {
  return activeModules(course).reduce((total, m) => total + m.lessons.length, 0)
}

export function exerciseCount(course: CourseEntry): number {
  return activeModules(course).reduce(
    (total, m) => total + m.lessons.filter((l) => l.exercise).length,
    0,
  )
}

export function totalLessonCount(manifest: Manifest): number {
  return allActiveModules(manifest).reduce((total, m) => total + m.lessons.length, 0)
}

export function totalExerciseCount(manifest: Manifest): number {
  return allActiveModules(manifest).reduce(
    (total, m) => total + m.lessons.filter((l) => l.exercise).length,
    0,
  )
}

/**
 * Modules whose bundled version differs from the server's. Drives the desktop
 * app's background content sync: it pulls only what actually moved.
 */
export function staleModules(local: Manifest, remote: Manifest): ModuleEntry[] {
  const localVersions = new Map(allActiveModules(local).map((m) => [m.id, m.version]))
  return allActiveModules(remote).filter((m) => localVersions.get(m.id) !== m.version)
}
