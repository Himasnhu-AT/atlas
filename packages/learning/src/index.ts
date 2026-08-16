/**
 * Navigation over a built content manifest.
 *
 * These are pure functions taking a manifest rather than reading `dist/`
 * themselves. The web app imports the manifest at build time and the desktop app
 * loads a bundled or freshly synced copy, so neither can share a single import
 * of it. Keeping the functions pure also makes them testable without a build.
 */

import type { LessonEntry, Manifest, ModuleEntry, Track } from './schema'

export * from './schema'

/** Modules a student can see, in display order. Hidden modules never appear. */
export function activeModules(manifest: Manifest): ModuleEntry[] {
  return manifest.modules.filter((m) => m.isActive).sort((a, b) => a.order - b.order)
}

export function modulesInTrack(manifest: Manifest, track: Track): ModuleEntry[] {
  return activeModules(manifest).filter((m) => m.track === track)
}

export function getModule(manifest: Manifest, slug: string): ModuleEntry | undefined {
  return activeModules(manifest).find((m) => m.slug === slug)
}

export function getModuleById(manifest: Manifest, id: string): ModuleEntry | undefined {
  return activeModules(manifest).find((m) => m.id === id)
}

export function getLesson(
  manifest: Manifest,
  moduleSlug: string,
  lessonSlug: string,
): { module: ModuleEntry; lesson: LessonEntry } | undefined {
  const module = getModule(manifest, moduleSlug)
  const lesson = module?.lessons.find((l) => l.slug === lessonSlug)
  return module && lesson ? { module, lesson } : undefined
}

/**
 * Every lesson in reading order, flattened across modules. This is the spine of
 * prev/next navigation and of `generateStaticParams` on the web.
 */
export function lessonSequence(
  manifest: Manifest,
): { module: ModuleEntry; lesson: LessonEntry }[] {
  return activeModules(manifest).flatMap((module) =>
    [...module.lessons]
      .sort((a, b) => a.order - b.order)
      .map((lesson) => ({ module, lesson })),
  )
}

export function neighbours(manifest: Manifest, lessonId: string) {
  const sequence = lessonSequence(manifest)
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

export function lessonCount(manifest: Manifest): number {
  return activeModules(manifest).reduce((total, m) => total + m.lessons.length, 0)
}

export function exerciseCount(manifest: Manifest): number {
  return activeModules(manifest).reduce(
    (total, m) => total + m.lessons.filter((l) => l.exercise).length,
    0,
  )
}

/**
 * Modules whose bundled version differs from the server's. Drives the desktop
 * app's background content sync: it pulls only what actually moved.
 */
export function staleModules(local: Manifest, remote: Manifest): ModuleEntry[] {
  const localVersions = new Map(local.modules.map((m) => [m.id, m.version]))
  return remote.modules.filter((m) => localVersions.get(m.id) !== m.version)
}
