import manifest from '@learn/learning/manifest'

import { json, route } from '@/lib/server/respond'

/**
 * The manifest the desktop app diffs against its bundled copy to decide which
 * modules to re-sync. Public: it is metadata about content that ships inside
 * both apps anyway.
 */
export const GET = route(async () =>
  json({
    contentVersion: manifest.contentVersion,
    builtAt: manifest.builtAt,
    modules: manifest.modules.map((module) => ({
      id: module.id,
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
  }),
)
