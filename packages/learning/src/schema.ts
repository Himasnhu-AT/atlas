import { z } from 'zod'

/**
 * The content schema. Everything the build pipeline validates, and the only
 * shape the web and desktop apps are allowed to assume.
 *
 * Authoring lives in two files per module:
 *   modules/<dir>/module.yaml   -> ModuleMeta
 *   modules/<dir>/<n>-<slug>.mdx -> LessonFrontmatter + body
 */

export const TRACKS = ['base', 'cli', 'agent', 'frameworks', 'projects'] as const
export const DIFFICULTIES = ['beginner', 'intermediate', 'advanced'] as const
export const EXERCISE_LANGUAGES = ['python', 'bash'] as const

export type Track = (typeof TRACKS)[number]
export type Difficulty = (typeof DIFFICULTIES)[number]
export type ExerciseLanguage = (typeof EXERCISE_LANGUAGES)[number]

/** `stage-3`, `cli-a1`. Lowercase, digits, single hyphens. */
const moduleId = z
  .string()
  .regex(/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/, 'module id must be lowercase kebab-case')

/** `stage-3.react-loop`. A module id, a dot, then a lesson slug. */
const lessonId = z
  .string()
  .regex(
    /^[a-z][a-z0-9]*(-[a-z0-9]+)*\.[a-z][a-z0-9]*(-[a-z0-9]+)*$/,
    'lesson id must be <module-id>.<lesson-slug>',
  )

/** Semver, no prerelease. Bumping this is what tells a desktop client to re-sync. */
const version = z.string().regex(/^\d+\.\d+\.\d+$/, 'version must be MAJOR.MINOR.PATCH')

/**
 * An exercise, as declared in a lesson's frontmatter.
 *
 * `scaffold` is the student's starting buffer: signatures and docstrings with
 * empty bodies. `reference` is a complete worked solution, shown only when the
 * student asks for it. `test` grades the student's file and must pass against
 * `reference` for the build to succeed.
 */
export const ExerciseSpec = z.object({
  /** Directory name under the module's `exercises/`. */
  id: z
    .string()
    .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'exercise id must be lowercase kebab-case'),
  language: z.enum(EXERCISE_LANGUAGES).default('python'),
  scaffold: z.string().default('scaffold.py'),
  reference: z.string().default('reference.py'),
  test: z.string().default('test.py'),
  /**
   * Minutes of struggle before the app offers the reference. Struggling is
   * useful; grinding is not.
   */
  timeboxMinutes: z.number().int().positive().max(240).default(20),
})
export type ExerciseSpec = z.infer<typeof ExerciseSpec>

export const ModuleMeta = z.object({
  id: moduleId,
  slug: z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/),
  name: z.string().min(1).max(80),
  summary: z.string().min(1).max(300),
  version,
  track: z.enum(TRACKS),
  order: z.number().int().nonnegative(),
  isActive: z.boolean().default(true),
  prerequisites: z.array(moduleId).default([]),
  difficulty: z.enum(DIFFICULTIES),
  estimatedHours: z.number().positive().max(100),
})
export type ModuleMeta = z.infer<typeof ModuleMeta>

export const LessonFrontmatter = z.object({
  id: lessonId,
  title: z.string().min(1).max(120),
  summary: z.string().min(1).max(300),
  order: z.number().int().nonnegative(),
  estimatedMinutes: z.number().int().positive().max(600),
  exercise: ExerciseSpec.optional(),
})
export type LessonFrontmatter = z.infer<typeof LessonFrontmatter>

/**
 * A lesson as it appears in the manifest. The body is deliberately absent:
 * the manifest is the navigation tree and stays small enough to ship to a
 * client on every page load. Bodies live in `dist/lessons/<id>.json`.
 */
export const LessonEntry = LessonFrontmatter.extend({
  moduleId,
  slug: z.string(),
  /** Heading anchors, for the in-page outline. */
  headings: z.array(
    z.object({ depth: z.number().int().min(2).max(4), text: z.string(), slug: z.string() }),
  ),
  wordCount: z.number().int().nonnegative(),
})
export type LessonEntry = z.infer<typeof LessonEntry>

export const ModuleEntry = ModuleMeta.extend({
  lessons: z.array(LessonEntry),
})
export type ModuleEntry = z.infer<typeof ModuleEntry>

export const Manifest = z.object({
  /** Hash of every module version. Changes whenever any content changes. */
  contentVersion: z.string(),
  builtAt: z.string(),
  modules: z.array(ModuleEntry),
})
export type Manifest = z.infer<typeof Manifest>

/** One lesson body, rendered. Written to `dist/lessons/<id>.json`. */
export const CompiledLesson = z.object({
  id: lessonId,
  moduleId,
  /**
   * The lesson body as plain HTML, syntax highlighting already applied.
   *
   * Rendered here rather than shipped as a JavaScript function the apps
   * evaluate, so neither app needs an MDX runtime and neither needs a Content
   * Security Policy permitting `unsafe-eval`. The Tauri window refuses
   * generated code outright, which is the correct posture for a desktop app.
   */
  html: z.string(),
  /** Files copied into the student's workspace, keyed by filename. */
  exerciseFiles: z.record(z.string(), z.string()).optional(),
  /**
   * Hash of every file in `exerciseFiles`, so a client can tell whether the
   * exercise under a student's `solution.py` is the one they last worked
   * against.
   *
   * The desktop app overwrites the support files on every open and never
   * overwrites `solution.py`, which is right: their work survives, and a stale
   * `test.py` cannot be edited into passing. The gap is that a rewritten
   * exercise then meets an old `solution.py` and fails on an `ImportError`
   * naming a symbol the lesson told them to write, which is the one failure the
   * course promises is never their own logic.
   *
   * Every shipped file feeds the hash, `mockllm.py` included, because a change
   * to the mock client breaks a solution exactly as a change to `test.py` does.
   * The cost is that editing `mockllm.py` marks every exercise as moved. That is
   * the right side to err on: the client only shows a message, and a false alarm
   * is cheaper than the silent failure this exists to prevent.
   */
  exerciseHash: z.string().optional(),
})
export type CompiledLesson = z.infer<typeof CompiledLesson>
