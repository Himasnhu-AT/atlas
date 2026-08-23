import { manifest } from '@/lib/content'
import { json, route } from '@/lib/server/respond'

/**
 * The manifest the desktop app diffs against its bundled copy to decide what to
 * re-sync. Public: it is metadata about content that ships inside both apps
 * anyway.
 *
 * Modules stay flat in the response and carry their `courseId`, because the
 * client's question is only ever "which of these moved". `staleModules` in
 * `@learn/learning` compares by module id and version, so nesting them by course
 * here would make every caller unnest them again.
 */
export const GET = route(async () =>
  json({
    contentVersion: manifest.contentVersion,
    builtAt: manifest.builtAt,
    courses: manifest.courses.map((course) => ({
      id: course.id,
      slug: course.slug,
      name: course.name,
      version: course.version,
      isActive: course.isActive,
      order: course.order,
      tracks: course.tracks,
    })),
    modules: manifest.courses.flatMap((course) =>
      course.modules.map((module) => ({
        id: module.id,
        courseId: course.id,
        slug: module.slug,
        name: module.name,
        version: module.version,
        isActive: module.isActive,
        prerequisites: module.prerequisites,
        track: module.track,
        order: module.order,
        difficulty: module.difficulty,
        estimatedHours: module.estimatedHours,
        lessonCount: module.lessons.length,
      })),
    ),
  }),
)
