import { readFile } from 'node:fs/promises'
import path from 'node:path'

import {
  activeCourses as activeCoursesOf,
  activeModules as activeModulesOf,
  allActiveModules,
  findLessonById,
  getCourse,
  getLesson,
  getModule,
  lessonSequence as lessonSequenceOf,
  neighbours as neighboursOf,
  trackOf,
  type CourseEntry,
  type Manifest,
  type ModuleEntry,
} from '@atlas/learning'
import rawManifest from '@atlas/learning/manifest'

/**
 * Reading the built content from the server.
 *
 * The manifest is imported directly, so navigation costs nothing at runtime.
 * Lesson bodies are read from disk on demand and cached, because inlining every
 * compiled document into the server bundle would be wasteful when a request
 * needs exactly one.
 *
 * The navigation itself lives in `@atlas/learning` and is only bound to this
 * manifest here. It used to be reimplemented in this file, which is how the web
 * and the desktop app were able to disagree about reading order.
 */

/**
 * TypeScript infers a JSON import structurally, so unions the schema constrains
 * (`difficulty`, and every optional field) widen to `string` on the way in. The
 * file is written by the content build straight from `Manifest`, and the build
 * refuses to emit one that does not parse, so this is the boundary where the
 * declared type is reattached rather than a claim about unvalidated data.
 */
const manifest = rawManifest as unknown as Manifest

export { manifest }

export interface CompiledLesson {
  id: string
  moduleId: string
  courseId: string
  html: string
  exerciseFiles?: Record<string, string>
}

const LESSON_DIR = path.join(process.cwd(), '..', '..', 'packages', 'learning', 'dist', 'lessons')

const cache = new Map<string, CompiledLesson>()

export async function loadLesson(lessonId: string): Promise<CompiledLesson | null> {
  const cached = cache.get(lessonId)
  if (cached) return cached

  // The id comes from a URL segment. Reject anything that is not a plain
  // lesson id before it reaches the filesystem.
  if (!/^[a-z0-9]+(-[a-z0-9]+)*\.[a-z0-9]+(-[a-z0-9]+)*$/.test(lessonId)) return null

  try {
    const raw = await readFile(path.join(LESSON_DIR, `${lessonId}.json`), 'utf8')
    const lesson = JSON.parse(raw) as CompiledLesson
    cache.set(lessonId, lesson)
    return lesson
  } catch {
    return null
  }
}

export const activeCourses = () => activeCoursesOf(manifest)
export const findCourse = (slug: string) => getCourse(manifest, slug)
export const activeModules = (course: CourseEntry) => activeModulesOf(course)
export const everyModule = () => allActiveModules(manifest)
export const findModule = (course: CourseEntry, slug: string) => getModule(course, slug)
export const lessonSequence = (course: CourseEntry) => lessonSequenceOf(course)
export const neighbours = (course: CourseEntry, lessonId: string) => neighboursOf(course, lessonId)
export const findLesson = (course: CourseEntry, moduleSlug: string, lessonSlug: string) =>
  getLesson(course, moduleSlug, lessonSlug) ?? null
export const locateLesson = (lessonId: string) => findLessonById(manifest, lessonId)
export const track = (course: CourseEntry, module: ModuleEntry) => trackOf(course, module)

/**
 * Every exercise in the catalogue, keyed by id, with the course and module that
 * own it. The build guarantees these ids are unique across every course.
 */
export function exerciseIndex() {
  const index = new Map<string, { courseId: string; moduleId: string; lessonId: string }>()
  for (const course of activeCourses()) {
    for (const module of activeModulesOf(course)) {
      for (const lesson of module.lessons) {
        if (!lesson.exercise) continue
        index.set(lesson.exercise.id, {
          courseId: course.id,
          moduleId: module.id,
          lessonId: lesson.id,
        })
      }
    }
  }
  return index
}

/** Every (course, module, lesson) triple, for static generation across courses. */
export function everyLesson() {
  return activeCourses().flatMap((course) =>
    lessonSequenceOf(course).map(({ module, lesson }) => ({ course, module, lesson })),
  )
}

/**
 * Prerequisite ids resolved to the names a student would recognise.
 *
 * Scoped to one course, because a prerequisite cannot cross a course boundary
 * and the build refuses one that tries.
 */
export function prerequisiteNames(course: CourseEntry, ids: string[]): string {
  const byId = new Map(activeModulesOf(course).map((module) => [module.id, module.name]))
  return ids.map((id) => byId.get(id) ?? id).join(' and ')
}
