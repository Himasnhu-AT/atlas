/**
 * Loading compiled lesson bodies and exercise files from the bundle.
 *
 * The content build emits one JSON per lesson holding the compiled MDX and,
 * where there is an exercise, every file it needs. Those are bundled into the
 * app so a learner can work on a plane, and loaded lazily so opening the app
 * does not parse nineteen documents nobody asked for.
 */

export interface CompiledLesson {
  id: string
  moduleId: string
  /** The body as HTML, syntax highlighting already applied by the build. */
  html: string
  /** Exercise files keyed by filename, present only for lessons with one. */
  exerciseFiles?: Record<string, string>
  /**
   * Hash of every file above, written beside the learner's `solution.py` so a
   * later open can tell whether the exercise moved underneath their work.
   */
  exerciseHash?: string
}

/**
 * Vite resolves this glob at build time, so every lesson ends up in the bundle
 * as its own chunk. The relative path reaches into the workspace package
 * because `dist/` is build output rather than something with an export map.
 */
const loaders = import.meta.glob<{ default: CompiledLesson }>(
  '../../../../packages/learning/dist/lessons/*.json',
)

const byId = new Map<string, () => Promise<{ default: CompiledLesson }>>()
for (const [path, loader] of Object.entries(loaders)) {
  const id = path.split('/').pop()?.replace(/\.json$/, '')
  if (id) byId.set(id, loader)
}

const cache = new Map<string, CompiledLesson>()

export async function loadLesson(lessonId: string): Promise<CompiledLesson | null> {
  const cached = cache.get(lessonId)
  if (cached) return cached

  const loader = byId.get(lessonId)
  if (!loader) return null

  const loaded = (await loader()).default
  cache.set(lessonId, loaded)
  return loaded
}

/** Whether the bundle actually contains any lessons, for a clearer error. */
export function bundledLessonCount(): number {
  return byId.size
}
