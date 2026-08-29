import { z } from 'zod'

/**
 * The content schema. Everything the build pipeline validates, and the only
 * shape the web and desktop apps are allowed to assume.
 *
 * Authoring lives in three files:
 *   courses/<dir>/course.yaml                    -> CourseMeta
 *   courses/<dir>/modules/<dir>/module.yaml      -> ModuleMeta
 *   courses/<dir>/modules/<dir>/<n>-<slug>.mdx   -> LessonFrontmatter + body
 *
 * A course is the unit a student chooses. Modules live inside one, and nothing
 * crosses a course boundary: a prerequisite naming a module in another course
 * fails the build.
 */

export const DIFFICULTIES = ['beginner', 'intermediate', 'advanced'] as const
export const EXERCISE_LANGUAGES = ['python', 'bash'] as const

export type Difficulty = (typeof DIFFICULTIES)[number]
export type ExerciseLanguage = (typeof EXERCISE_LANGUAGES)[number]

/**
 * A track is a grouping of modules inside one course, and it is deliberately
 * NOT a global enum.
 *
 * It used to be `base | cli | agent | frameworks | projects`, which are words
 * that only mean anything to the AI course. A data engineering course has no
 * "agent" track and a Rust course has no "frameworks" track in that sense, so a
 * shared enum would force every new course to either misuse an existing word or
 * widen a type that every other course then has to ignore. Each course declares
 * its own tracks in `course.yaml`, and the build checks that every module names
 * one its own course declared.
 */
export type Track = string

/** `ai-tool-use`, `de-pipelines`. Lowercase, digits, single hyphens. */
const moduleId = z
  .string()
  .regex(/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/, 'module id must be lowercase kebab-case')

/** `ai-tool-use.react-loop`. A module id, a dot, then a lesson slug. */
const lessonId = z
  .string()
  .regex(
    /^[a-z][a-z0-9]*(-[a-z0-9]+)*\.[a-z][a-z0-9]*(-[a-z0-9]+)*$/,
    'lesson id must be <module-id>.<lesson-slug>',
  )

/** `ai-agents`, `data-engineering`. Lowercase, digits, single hyphens. */
const courseId = z
  .string()
  .regex(/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/, 'course id must be lowercase kebab-case')

const slug = z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'slug must be lowercase kebab-case')

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
  /**
   * Whether this can be graded in a browser, and why not when it cannot.
   *
   * Not authored. The build derives it from the exercise's own imports and
   * writes it into the manifest, so a lesson page knows before it loads a
   * WebAssembly runtime whether there is any point. See `src/browser.ts` for
   * what is unsupported and how that was measured.
   */
  browser: z
    .object({ runnable: z.boolean(), reason: z.string().optional() })
    .optional(),
})
export type ExerciseSpec = z.infer<typeof ExerciseSpec>

/**
 * What one test is checking, in words the learner has not read before.
 *
 * `test_ignores_braces_inside_strings` failing tells a learner what they
 * already knew, which is that something about braces went wrong. "You did not
 * handle: a closing brace that appears inside a string literal" tells them the
 * case they forgot, which is the only thing they were actually missing.
 *
 * None of the 1775 test methods in this repo carries a docstring, so there is
 * nothing to derive this from. It is authored, and the build gates on it.
 */
export const ExerciseCase = z.object({
  /**
   * One clause naming the input or the situation, not the assertion. Lower
   * case and no trailing period: the app writes "You did not handle: {this}."
   */
  condition: z.string().min(8).max(160),
  /**
   * Escalating. The first names the misconception, the last is close to the
   * answer. Fewer than three is allowed; more is a lesson, and a lesson goes
   * in the lesson.
   */
  hints: z.array(z.string().min(8).max(400)).min(1).max(3),
  /** A lesson id in the same course. Nothing crosses a course boundary. */
  concept: z.string().max(160).optional(),
})
export type ExerciseCase = z.infer<typeof ExerciseCase>

/**
 * An exercise's case map: `exercises/<id>/cases.yaml`.
 *
 * Keyed on `ClassName.test_method`, the same id the shared runner reports, so
 * a key that validates cannot fail to match at runtime. The build discovers
 * the real key set by asking unittest's loader rather than by reading the file
 * with an AST, because the loader is what will actually run.
 */
export const ExerciseCases = z.object({
  version: z.literal(1),
  cases: z.record(
    z.string().regex(/^[A-Za-z_]\w*\.[A-Za-z_]\w*$/, 'a case key is ClassName.test_method'),
    ExerciseCase,
  ),
})
export type ExerciseCases = z.infer<typeof ExerciseCases>

/**
 * Interactive visual sandbox / game spec declared in a lesson's frontmatter.
 */
export const InteractiveSpec = z.object({
  type: z.string().min(1),
  props: z.record(z.string(), z.any()).default({}),
})
export type InteractiveSpec = z.infer<typeof InteractiveSpec>

export const LessonFrontmatter = z.object({
  id: lessonId,
  title: z.string().min(1).max(120),
  summary: z.string().min(1).max(300),
  order: z.number().int().nonnegative(),
  estimatedMinutes: z.number().int().positive().max(600),
  exercise: ExerciseSpec.optional(),
  interactive: InteractiveSpec.optional(),
})
export type LessonFrontmatter = z.infer<typeof LessonFrontmatter>

/** One track a course declares. `id` is what a module's `track` names. */
export const TrackMeta = z.object({
  id: slug,
  name: z.string().min(1).max(60),
  note: z.string().min(1).max(200).optional(),
})
export type TrackMeta = z.infer<typeof TrackMeta>

/**
 * A course: the unit a student picks up. `courses/<dir>/course.yaml`.
 *
 * `lib` names a directory whose files are copied into every exercise workspace
 * in this course, rather than installed. The AI course ships `mockllm.py` that
 * way; a data course ships its own fixture generator, and neither knows the
 * other exists.
 */
export const CourseMeta = z.object({
  id: courseId,
  slug,
  name: z.string().min(1).max(80),
  summary: z.string().min(1).max(400),
  version,
  order: z.number().int().nonnegative(),
  isActive: z.boolean().default(true),
  tracks: z.array(TrackMeta).min(1),
  lib: z.string().default('lib'),
})
export type CourseMeta = z.infer<typeof CourseMeta>

export const ModuleMeta = z.object({
  id: moduleId,
  slug,
  name: z.string().min(1).max(80),
  summary: z.string().min(1).max(300),
  version,
  /** Validated against the enclosing course's declared tracks by the build. */
  track: z.string().min(1),
  order: z.number().int().nonnegative(),
  isActive: z.boolean().default(true),
  prerequisites: z.array(moduleId).default([]),
  difficulty: z.enum(DIFFICULTIES),
  estimatedHours: z.number().positive().max(100),
})
export type ModuleMeta = z.infer<typeof ModuleMeta>

/**
 * A lesson as it appears in the manifest. The body is deliberately absent:
 * the manifest is the navigation tree and stays small enough to ship to a
 * client on every page load. Bodies live in `dist/lessons/<id>.json`.
 */
export const LessonEntry = LessonFrontmatter.extend({
  moduleId,
  courseId,
  slug: z.string(),
  /** Heading anchors, for the in-page outline. */
  headings: z.array(
    z.object({ depth: z.number().int().min(2).max(4), text: z.string(), slug: z.string() }),
  ),
  wordCount: z.number().int().nonnegative(),
})
export type LessonEntry = z.infer<typeof LessonEntry>

export const ModuleEntry = ModuleMeta.extend({
  courseId,
  lessons: z.array(LessonEntry),
})
export type ModuleEntry = z.infer<typeof ModuleEntry>

export const CourseEntry = CourseMeta.extend({
  modules: z.array(ModuleEntry),
})
export type CourseEntry = z.infer<typeof CourseEntry>

export const Manifest = z.object({
  /** Hash of every course and module version. Changes when any content does. */
  contentVersion: z.string(),
  builtAt: z.string(),
  courses: z.array(CourseEntry),
})
export type Manifest = z.infer<typeof Manifest>

/** One lesson body, rendered. Written to `dist/lessons/<id>.json`. */
export const CompiledLesson = z.object({
  id: lessonId,
  moduleId,
  courseId,
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
   * Stage 1, as authored. Declared here at last: the build has always written
   * this field and this schema has never mentioned it, so both apps read an
   * undeclared key off the compiled artifact.
   */
  interactive: InteractiveSpec.optional(),
  /**
   * The exercise's case map, keyed on `ClassName.test_method`.
   *
   * It rides on the compiled lesson rather than in `exerciseFiles` for two
   * reasons: it must not be copied into the learner's workspace, and it must
   * not enter `exerciseHash`, or editing a hint would tell every learner mid
   * exercise that the exercise moved underneath them.
   */
  exerciseCases: z.record(z.string(), ExerciseCase).optional(),
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
