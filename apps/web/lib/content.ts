import { readFile } from 'node:fs/promises'
import path from 'node:path'

import manifest from '@learn/learning/manifest'

/**
 * Reading the built content from the server.
 *
 * The manifest is imported directly, so navigation costs nothing at runtime.
 * Lesson bodies are read from disk on demand and cached, because inlining
 * nineteen compiled MDX documents into the server bundle would be wasteful when
 * a request needs exactly one.
 */

export { manifest }

export interface CompiledLesson {
  id: string
  moduleId: string
  html: string
  exerciseFiles?: Record<string, string>
}

const LESSON_DIR = path.join(
  process.cwd(),
  '..',
  '..',
  'packages',
  'learning',
  'dist',
  'lessons',
)

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

export function activeModules() {
  return manifest.modules.filter((module) => module.isActive).sort((a, b) => a.order - b.order)
}

export function findModule(slug: string) {
  return activeModules().find((module) => module.slug === slug)
}

export function findLesson(moduleSlug: string, lessonSlug: string) {
  const module = findModule(moduleSlug)
  const lesson = module?.lessons.find((entry) => entry.slug === lessonSlug)
  return module && lesson ? { module, lesson } : null
}

/** Flat reading order, for prev/next and static generation. */
export function lessonSequence() {
  return activeModules().flatMap((module) =>
    [...module.lessons]
      .sort((a, b) => a.order - b.order)
      .map((lesson) => ({ module, lesson })),
  )
}

/** Prerequisite ids resolved to the names a student would recognise. */
export function prerequisiteNames(ids: string[]): string {
  const byId = new Map(activeModules().map((module) => [module.id, module.name]))
  return ids.map((id) => byId.get(id) ?? id).join(' and ')
}

export function neighbours(lessonId: string) {
  const sequence = lessonSequence()
  const index = sequence.findIndex((entry) => entry.lesson.id === lessonId)
  if (index === -1) return { previous: undefined, next: undefined }
  return { previous: sequence[index - 1], next: sequence[index + 1] }
}
