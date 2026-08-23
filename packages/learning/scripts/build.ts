/**
 * Content build. Parses every module and lesson, validates them, compiles the
 * MDX, and emits `dist/`.
 *
 * This is a gate, not a formatter. It exits non-zero on any of:
 *   - a module.yaml or lesson frontmatter that fails its schema
 *   - a duplicate module id, lesson id, or order collision
 *   - a prerequisite naming a module that does not exist, or a cycle
 *   - a lesson declaring an exercise whose directory or files are missing
 *   - a cross-lesson link pointing at a lesson that does not exist
 *   - a rendered lesson still carrying an unsubstituted `PLACEHOLDER_` token
 *   - an exercise whose reference solution does not pass its own test
 *   - an exercise whose scaffold PASSES that test, which means it teaches nothing
 *   - a Python file that will not parse, an import that needs pip, a scaffold
 *     whose signatures have drifted from the reference, or a reference still
 *     carrying a stub (see scripts/validate_exercise.py)
 *
 * The reference check is the point of the whole thing. A broken exercise cannot
 * ship. The scaffold check is its mirror: an exercise the student has nothing to
 * do in is broken too, and nothing else in the pipeline would notice.
 *
 * Usage: tsx scripts/build.ts [--check] [--watch]
 */

import { execFile } from 'node:child_process'
import { createHash } from 'node:crypto'
import { cp, mkdir, mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'

import rehypeShiki from '@shikijs/rehype'
import rehypeAutolinkHeadings from 'rehype-autolink-headings'
import rehypeSlug from 'rehype-slug'
import rehypeStringify from 'rehype-stringify'
import remarkGfm from 'remark-gfm'
import remarkParse from 'remark-parse'
import remarkRehype from 'remark-rehype'
import { unified } from 'unified'
import matter from 'gray-matter'
import { parse as parseYaml } from 'yaml'

import { CONTENT_TOKENS } from '../src/links'
import {
  type CourseEntry,
  CourseMeta,
  type LessonEntry,
  LessonFrontmatter,
  type Manifest,
  type ModuleEntry,
  ModuleMeta,
} from '../src/schema'

const execFileAsync = promisify(execFile)

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const COURSES_DIR = path.join(ROOT, 'courses')
const DIST_DIR = path.join(ROOT, 'dist')

/**
 * The student's working file. `scaffold.py` is copied to this name when the
 * exercise is first opened, and `test.py` imports from it. Keeping the name
 * fixed is what lets one test file grade both the student's attempt and the
 * reference solution.
 */
const SOLUTION_FILENAME = 'solution.py'

/**
 * A course's support library: the files copied into every exercise workspace in
 * that course rather than installed, so a student needs nothing but a Python
 * interpreter to run their first test.
 *
 * The AI course ships `mockllm.py` this way. A course declares the directory in
 * its `course.yaml`, and nothing outside that course sees it.
 */
type CourseLib = Record<string, string>

async function readCourseLib(courseDir: string, libDir: string): Promise<CourseLib> {
  const dir = path.join(courseDir, libDir)
  if (!existsSync(dir)) return {}
  const lib: CourseLib = {}
  for (const name of await readdir(dir)) {
    if (name === '__pycache__' || name.startsWith('.')) continue
    lib[name] = await readFile(path.join(dir, name), 'utf8')
  }
  return lib
}

/**
 * The rest of the exercise gate, in Python because it is checking Python. It
 * parses the exercise's files, compares the scaffold's surface against the
 * reference's, and runs the scaffold against the test to prove it fails. It
 * reports JSON on stdout so this file parses a result instead of scraping text.
 */
const VALIDATOR_PATH = path.join(ROOT, 'scripts', 'validate_exercise.py')

/**
 * How long one exercise gets. A reference solution against mockllm finishes in
 * about a second, so anything near this is a loop that never terminates, and
 * saying so beats a build that appears to hang.
 */
const EXERCISE_TIMEOUT_MS = 60_000

const problems: string[] = []
const fail = (where: string, message: string) => problems.push(`${where}: ${message}`)

type Heading = { depth: number; text: string; slug: string }

/**
 * Collects headings while remark walks the tree, so the outline comes from the
 * same parse as the body rather than a second regex pass over the source.
 */
function collectHeadings(sink: Heading[]) {
  return () => (tree: unknown) => {
    const walk = (node: any) => {
      if (node.type === 'heading' && node.depth >= 2 && node.depth <= 4) {
        const text = textOf(node)
        sink.push({ depth: node.depth, text, slug: slugify(text) })
      }
      for (const child of node.children ?? []) walk(child)
    }
    walk(tree)
  }
}

function textOf(node: any): string {
  if (typeof node.value === 'string') return node.value
  return (node.children ?? []).map(textOf).join('')
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

async function readDirs(parent: string): Promise<string[]> {
  if (!existsSync(parent)) return []
  const entries = await readdir(parent, { withFileTypes: true })
  return entries
    .filter((e) => e.isDirectory() && !e.name.startsWith('.'))
    .map((e) => e.name)
    .sort()
}

/**
 * Runs an exercise's test against its reference solution in a throwaway
 * directory, so a half-finished exercise never reaches a student.
 */
async function verifyReference(
  exerciseDir: string,
  spec: { reference: string; test: string },
  lib: CourseLib,
  where: string,
): Promise<void> {
  const scratch = await mkdtemp(path.join(tmpdir(), 'atlas-verify-'))
  try {
    await cp(exerciseDir, scratch, { recursive: true })
    for (const [name, contents] of Object.entries(lib)) {
      await writeFile(path.join(scratch, name), contents)
    }
    await cp(path.join(scratch, spec.reference), path.join(scratch, SOLUTION_FILENAME))

    const { stdout, stderr } = await execFileAsync('python3', [spec.test], {
      cwd: scratch,
      timeout: EXERCISE_TIMEOUT_MS,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    })
    void stdout
    void stderr
  } catch (error) {
    const err = error as {
      code?: number | string
      killed?: boolean
      signal?: string
      stdout?: string
      stderr?: string
    }
    if (err.code === 'ENOENT') {
      fail(where, 'python3 not found, cannot verify the reference solution')
      return
    }
    // execFile kills the child on timeout, which otherwise surfaces as a test
    // failure with no output at all.
    if (err.killed) {
      fail(
        where,
        `${spec.test} did not finish within ${EXERCISE_TIMEOUT_MS / 1000}s against ` +
          `${spec.reference} and was killed. Against mockllm a whole suite runs in ` +
          `about a second, so look for a loop with no exit: an agent loop missing its ` +
          `finish_reason check, or a max_steps guard that never decrements.`,
      )
      return
    }
    const output = `${err.stdout ?? ''}${err.stderr ?? ''}`.trim()
    const tail = output.split('\n').slice(-15).join('\n')
    fail(where, `reference solution does not pass ${spec.test}\n${indent(tail)}`)
  } finally {
    await rm(scratch, { recursive: true, force: true })
  }
}

type ValidatorResult = { problems: string[]; parsed: string[] }

/**
 * The static and structural half of the exercise gate, plus the scaffold run.
 *
 * Returns the names of the files that parsed, so the caller can skip the
 * reference run when a syntax error already explains everything. Running it
 * anyway would bury a one line answer under a screen of unittest output, which
 * is the thing these checks exist to stop.
 */
async function validateExercise(
  exerciseDir: string,
  spec: { scaffold: string; reference: string; test: string },
  libDir: string,
  where: string,
): Promise<string[] | null> {
  let raw: string
  try {
    const { stdout } = await execFileAsync(
      'python3',
      [
        VALIDATOR_PATH,
        '--dir',
        exerciseDir,
        '--lib',
        libDir,
        '--scaffold',
        spec.scaffold,
        '--reference',
        spec.reference,
        '--test',
        spec.test,
        '--timeout',
        String(EXERCISE_TIMEOUT_MS / 1000),
      ],
      {
        timeout: EXERCISE_TIMEOUT_MS * 2,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
        maxBuffer: 8 * 1024 * 1024,
      },
    )
    raw = stdout
  } catch (error) {
    const err = error as { code?: number | string; killed?: boolean; stderr?: string }
    if (err.code === 'ENOENT') {
      fail(where, 'python3 not found, cannot validate the exercise')
      return null
    }
    if (err.killed) {
      fail(where, `validate_exercise.py was killed after ${EXERCISE_TIMEOUT_MS / 500}s`)
      return null
    }
    fail(where, `validate_exercise.py failed\n${indent((err.stderr ?? '').trim())}`)
    return null
  }

  let result: ValidatorResult
  try {
    result = JSON.parse(raw) as ValidatorResult
  } catch {
    fail(where, `validate_exercise.py produced output that is not JSON\n${indent(raw.trim())}`)
    return null
  }

  for (const problem of result.problems) {
    fail(where, problem.includes('\n') ? problem.replace(/\n/g, `\n${'      '}`) : problem)
  }
  return result.parsed
}

/**
 * Replaces the tokens declared in `src/links.ts` in a rendered lesson body.
 *
 * A lesson that needs the provider offer writes the token, never the value, so
 * the offer is editable in one place. Doing this on the rendered HTML rather
 * than the MDX source means a token inside a code sample is substituted along
 * with the prose around it.
 *
 * Anything still matching the token shape after the pass is a problem, and it
 * fails the build. A retired or misspelled token is otherwise invisible: it
 * renders as shouting uppercase in the middle of a paragraph, or worse, as an
 * `href` the student clicks and gets a 404 from. This is the same reasoning as
 * the reference check. A lesson that lies to the reader cannot ship.
 */
const TOKEN_SHAPE = /PLACEHOLDER_[A-Z0-9_]+/g

function substituteTokens(html: string, where: string): string {
  let out = html
  for (const [token, value] of Object.entries(CONTENT_TOKENS)) {
    out = out.split(token).join(value)
  }
  const leftover = [...new Set(out.match(TOKEN_SHAPE) ?? [])]
  if (leftover.length > 0) {
    fail(
      where,
      `unsubstituted content token(s): ${leftover.join(', ')}. ` +
        `Tokens are declared in src/links.ts as CONTENT_TOKENS.`,
    )
  }
  return out
}

/**
 * A stable hash of an exercise's shipped files.
 *
 * Filenames are sorted and both name and contents feed the digest, so renaming a
 * file registers as a change and a `Record` whose keys arrive in a different
 * order does not. A client stores this beside the student's `solution.py` and
 * compares on open: a difference means the exercise moved underneath work that
 * is already there, which is the one case where a failing test is not the
 * student's bug.
 */
function hashFiles(files: Record<string, string> | undefined): string | undefined {
  if (!files) return undefined
  const digest = createHash('sha256')
  for (const name of Object.keys(files).sort()) {
    digest.update(name)
    digest.update('\0')
    digest.update(files[name]!)
    digest.update('\0')
  }
  return digest.digest('hex').slice(0, 12)
}

const indent = (text: string) =>
  text
    .split('\n')
    .map((line) => `      ${line}`)
    .join('\n')

async function buildModule(
  course: { id: string; dir: string; tracks: { id: string }[] },
  lib: CourseLib,
  libDir: string,
  dir: string,
): Promise<ModuleEntry | null> {
  const moduleDir = path.join(COURSES_DIR, course.dir, 'modules', dir)
  const metaPath = path.join(moduleDir, 'module.yaml')
  const at = `courses/${course.dir}/modules/${dir}`

  if (!existsSync(metaPath)) {
    fail(at, 'missing module.yaml')
    return null
  }

  // A malformed module.yaml must report as a content problem, not as an
  // unhandled YAML exception with a stack trace. An unquoted colon in a summary
  // is the usual cause and the message says so.
  let rawMeta: unknown
  try {
    rawMeta = parseYaml(await readFile(metaPath, 'utf8'))
  } catch (error) {
    const detail = (error as Error).message.split('\n')[0]
    fail(
      `${at}/module.yaml`,
      `is not valid YAML: ${detail}. A value containing ": " must be quoted.`,
    )
    return null
  }

  const metaResult = ModuleMeta.safeParse(rawMeta)
  if (!metaResult.success) {
    for (const issue of metaResult.error.issues) {
      fail(`${at}/module.yaml`, `${issue.path.join('.') || '(root)'} ${issue.message}`)
    }
    return null
  }
  const meta = metaResult.data

  // A module names a track, and the track has to be one its own course declared.
  // This is what replaces the old global enum: the check is real, but the
  // vocabulary is the course's own.
  if (!course.tracks.some((t) => t.id === meta.track)) {
    fail(
      `${at}/module.yaml`,
      `track "${meta.track}" is not declared by course ${course.id}. ` +
        `It declares: ${course.tracks.map((t) => t.id).join(', ')}.`,
    )
  }

  const files = (await readdir(moduleDir)).filter((f) => f.endsWith('.mdx')).sort()
  if (files.length === 0) fail(at, 'no .mdx lessons')

  const lessons: LessonEntry[] = []
  const compiled: {
    id: string
    html: string
    exerciseFiles?: Record<string, string>
    exerciseHash?: string
  }[] = []

  for (const file of files) {
    const where = `${at}/${file}`
    const raw = await readFile(path.join(moduleDir, file), 'utf8')
    const { data, content } = matter(raw)

    const parsed = LessonFrontmatter.safeParse(data)
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        fail(where, `${issue.path.join('.') || '(root)'} ${issue.message}`)
      }
      continue
    }
    const front = parsed.data

    if (!front.id.startsWith(`${meta.id}.`)) {
      fail(where, `lesson id "${front.id}" does not start with "${meta.id}."`)
      continue
    }

    const headings: Heading[] = []
    let html: string
    try {
      // Rendered to plain HTML here rather than to a JavaScript function that
      // the apps evaluate at runtime. Lessons are markdown with no interactive
      // components, so nothing is lost, and it means neither app needs an MDX
      // runtime or a Content Security Policy that permits `unsafe-eval`. The
      // Tauri window in particular refuses to evaluate generated code, which is
      // the correct posture for a desktop app.
      const file = await unified()
        .use(remarkParse)
        .use(remarkGfm)
        .use(collectHeadings(headings))
        .use(remarkRehype)
        .use(rehypeSlug)
        .use(rehypeAutolinkHeadings, { behavior: 'wrap' })
        // A single theme, because the product has a single theme. Passing a
        // light/dark pair makes Shiki emit both palettes as CSS variables plus
        // a prefers-color-scheme block on every token, which would be dead
        // weight in all twenty lessons.
        .use(rehypeShiki, { theme: 'github-light' })
        .use(rehypeStringify)
        .process(content)
      html = substituteTokens(String(file), where)
    } catch (error) {
      fail(where, `markdown failed to render: ${(error as Error).message}`)
      continue
    }

    let exerciseFiles: Record<string, string> | undefined
    if (front.exercise) {
      const spec = front.exercise
      const exerciseDir = path.join(moduleDir, 'exercises', spec.id)

      if (!existsSync(exerciseDir)) {
        fail(where, `exercise directory missing: exercises/${spec.id}`)
      } else {
        const required = [spec.scaffold, spec.reference, spec.test]
        const missing = required.filter((f) => !existsSync(path.join(exerciseDir, f)))
        if (missing.length > 0) {
          fail(where, `exercise ${spec.id} is missing ${missing.join(', ')}`)
        } else {
          const exerciseAt = `${where} (exercise ${spec.id})`
          const parsed = await validateExercise(exerciseDir, spec, libDir, exerciseAt)
          // A file that will not parse cannot fail its test in any informative
          // way, so the syntax error stands on its own. A null result means the
          // validator itself could not run, and the reference check still should.
          const parseable =
            parsed === null ||
            (parsed.includes(spec.reference) && parsed.includes(spec.test))
          if (parseable) await verifyReference(exerciseDir, spec, lib, exerciseAt)

          exerciseFiles = { ...lib }
          for (const name of await readdir(exerciseDir)) {
            if (name === '__pycache__') continue
            exerciseFiles[name] = await readFile(path.join(exerciseDir, name), 'utf8')
          }
        }
      }
    }

    const slug = front.id.slice(meta.id.length + 1)
    lessons.push({
      ...front,
      moduleId: meta.id,
      courseId: course.id,
      slug,
      headings,
      wordCount: content.split(/\s+/).filter(Boolean).length,
    })
    compiled.push({ id: front.id, html, exerciseFiles, exerciseHash: hashFiles(exerciseFiles) })
  }

  lessons.sort((a, b) => a.order - b.order)
  assertUnique(lessons.map((l) => l.id), at, 'duplicate lesson id')
  assertUnique(lessons.map((l) => l.order), at, 'duplicate lesson order')

  if (!process.argv.includes('--check')) {
    await mkdir(path.join(DIST_DIR, 'lessons'), { recursive: true })
    for (const lesson of compiled) {
      await writeFile(
        path.join(DIST_DIR, 'lessons', `${lesson.id}.json`),
        JSON.stringify({ ...lesson, moduleId: meta.id, courseId: course.id }),
      )
    }
  }

  return { ...meta, courseId: course.id, lessons }
}

function assertUnique(values: unknown[], where: string, message: string) {
  const seen = new Set<unknown>()
  for (const value of values) {
    if (seen.has(value)) fail(where, `${message}: ${String(value)}`)
    seen.add(value)
  }
}

/**
 * `order` places a module in its course, not inside its track. Two modules
 * claiming one is the collision two people adding tracks at the same time
 * produce, and it decides what the catalogue renders first, so the message names
 * both sides.
 */
function checkOrders(modules: ModuleEntry[], where: string) {
  const byOrder = new Map<number, string[]>()
  for (const module of modules) {
    byOrder.set(module.order, [...(byOrder.get(module.order) ?? []), module.id])
  }
  const taken = new Set(byOrder.keys())
  for (const [order, ids] of byOrder) {
    if (ids.length === 1) continue
    let free = 0
    while (taken.has(free)) free += 1
    fail(
      where,
      `order ${order} is claimed by ${ids.join(' and ')}. Order is global across ` +
        `every track in a course, so one of them takes ${free} instead.`,
    )
  }
}

/** Prerequisites must name real modules, and must not form a cycle. */
function checkPrerequisites(modules: ModuleEntry[], where: string) {
  const byId = new Map(modules.map((m) => [m.id, m]))

  for (const module of modules) {
    for (const prereq of module.prerequisites) {
      if (!byId.has(prereq)) {
        fail(`module ${module.id}`, `prerequisite "${prereq}" does not exist`)
      }
    }
  }

  const state = new Map<string, 'visiting' | 'done'>()
  const visit = (id: string, trail: string[]): void => {
    if (state.get(id) === 'done') return
    if (state.get(id) === 'visiting') {
      fail(`${where} prerequisites`, `cycle: ${[...trail, id].join(' -> ')}`)
      return
    }
    state.set(id, 'visiting')
    for (const prereq of byId.get(id)?.prerequisites ?? []) visit(prereq, [...trail, id])
    state.set(id, 'done')
  }
  for (const module of modules) visit(module.id, [])
}

/**
 * A prerequisite may not reach into another course.
 *
 * Courses are the unit a student chooses, so one that cannot be started until
 * some module of an unrelated course is finished is not a course, it is a later
 * chapter of that one. `checkPrerequisites` already runs per course and would
 * report a cross-course prerequisite as "does not exist", which is true but
 * unhelpful, so this says what actually went wrong.
 */
function checkCourseBoundaries(courses: CourseEntry[]) {
  const owner = new Map<string, string>()
  for (const course of courses) {
    for (const module of course.modules) owner.set(module.id, course.id)
  }
  for (const course of courses) {
    for (const module of course.modules) {
      for (const prereq of module.prerequisites) {
        const from = owner.get(prereq)
        if (from && from !== course.id) {
          fail(
            `module ${module.id}`,
            `prerequisite "${prereq}" belongs to course ${from}. A prerequisite ` +
              `may not cross a course boundary: a course has to be startable on its own.`,
          )
        }
      }
    }
  }
}

/** Internal links are written as `lesson:<module-id>.<slug>`. */
function checkCrossLinks(modules: ModuleEntry[], bodies: Map<string, string>) {
  const known = new Set(modules.flatMap((m) => m.lessons.map((l) => l.id)))
  for (const [lessonId, body] of bodies) {
    for (const match of body.matchAll(/lesson:([a-z0-9.-]+)/g)) {
      const target = match[1]!
      if (!known.has(target)) {
        fail(`lesson ${lessonId}`, `links to unknown lesson "${target}"`)
      }
    }
  }
}

/**
 * A course, parsed and built. Returns null when `course.yaml` is missing or
 * malformed, so one bad course reports as a content problem rather than taking
 * the whole build down with a stack trace.
 */
async function buildCourse(dir: string, bodies: Map<string, string>): Promise<CourseEntry | null> {
  const courseDir = path.join(COURSES_DIR, dir)
  const metaPath = path.join(courseDir, 'course.yaml')
  const at = `courses/${dir}`

  if (!existsSync(metaPath)) {
    fail(at, 'missing course.yaml')
    return null
  }

  let rawMeta: unknown
  try {
    rawMeta = parseYaml(await readFile(metaPath, 'utf8'))
  } catch (error) {
    const detail = (error as Error).message.split('\n')[0]
    fail(`${at}/course.yaml`, `is not valid YAML: ${detail}. A value containing ": " must be quoted.`)
    return null
  }

  const metaResult = CourseMeta.safeParse(rawMeta)
  if (!metaResult.success) {
    for (const issue of metaResult.error.issues) {
      fail(`${at}/course.yaml`, `${issue.path.join('.') || '(root)'} ${issue.message}`)
    }
    return null
  }
  const meta = metaResult.data

  assertUnique(meta.tracks.map((t) => t.id), `${at}/course.yaml`, 'duplicate track id')

  const libDir = path.join(courseDir, meta.lib)
  const lib = await readCourseLib(courseDir, meta.lib)

  const moduleDirs = await readDirs(path.join(courseDir, 'modules'))
  if (moduleDirs.length === 0) {
    fail(at, 'no modules/ directory, or no modules in it')
    return null
  }

  const modules: ModuleEntry[] = []
  for (const moduleDirName of moduleDirs) {
    const moduleDir = path.join(courseDir, 'modules', moduleDirName)
    for (const file of (await readdir(moduleDir)).filter((f) => f.endsWith('.mdx'))) {
      const { data, content } = matter(await readFile(path.join(moduleDir, file), 'utf8'))
      if (typeof data.id === 'string') bodies.set(data.id, content)
    }
    const built = await buildModule({ ...meta, dir }, lib, libDir, moduleDirName)
    if (built) modules.push(built)
  }

  modules.sort((a, b) => a.order - b.order)
  assertUnique(modules.map((m) => m.id), at, 'duplicate module id')
  checkOrders(modules, at)
  checkPrerequisites(modules, at)

  return { ...meta, modules }
}

async function main() {
  const check = process.argv.includes('--check')

  if (!check) await rm(DIST_DIR, { recursive: true, force: true })

  const dirs = await readDirs(COURSES_DIR)
  if (dirs.length === 0) {
    console.error('No courses found in courses/. Nothing to build.')
    process.exit(1)
  }

  const bodies = new Map<string, string>()
  const courses: CourseEntry[] = []
  for (const dir of dirs) {
    const built = await buildCourse(dir, bodies)
    if (built) courses.push(built)
  }

  courses.sort((a, b) => a.order - b.order)
  assertUnique(courses.map((c) => c.id), 'courses', 'duplicate course id')
  assertUnique(courses.map((c) => c.slug), 'courses', 'duplicate course slug')
  assertUnique(courses.map((c) => c.order), 'courses', 'duplicate course order')

  const allModules = courses.flatMap((c) => c.modules)

  // Module and exercise ids are the natural keys the platform stores progress
  // and awards against, so they have to be unique across the whole catalogue and
  // not merely within a course. Neither was checked before there was more than
  // one course, and exercise ids were unique by luck rather than by rule.
  assertUnique(allModules.map((m) => m.id), 'courses', 'duplicate module id across courses')
  assertUnique(
    allModules.flatMap((m) => m.lessons.flatMap((l) => (l.exercise ? [l.exercise.id] : []))),
    'courses',
    'duplicate exercise id across courses',
  )

  checkCrossLinks(allModules, bodies)
  checkCourseBoundaries(courses)

  if (problems.length > 0) {
    console.error(`\nContent build failed with ${problems.length} problem(s):\n`)
    for (const problem of problems) console.error(`  ${problem}`)
    console.error('')
    process.exit(1)
  }

  const contentVersion = createHash('sha256')
    .update(
      courses
        .map((c) => `${c.id}@${c.version}:${c.modules.map((m) => `${m.id}@${m.version}`).join(',')}`)
        .join('|'),
    )
    .digest('hex')
    .slice(0, 12)

  const manifest: Manifest = {
    contentVersion,
    builtAt: new Date().toISOString(),
    courses,
  }

  if (!check) {
    await mkdir(DIST_DIR, { recursive: true })
    await writeFile(path.join(DIST_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2))
  }

  const lessonCount = allModules.reduce((n, m) => n + m.lessons.length, 0)
  const exerciseCount = allModules.reduce(
    (n, m) => n + m.lessons.filter((l) => l.exercise).length,
    0,
  )
  console.log(
    `${check ? 'Checked' : 'Built'} ${courses.length} course(s), ${allModules.length} modules, ` +
      `${lessonCount} lessons, ${exerciseCount} exercises. Content version ${contentVersion}.`,
  )
}

await main()
