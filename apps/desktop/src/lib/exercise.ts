import { SOLUTION_FILE, exerciseDir, type LessonRef } from './content'
import { exerciseState, type ExerciseState } from './exerciseState'
import { loadLesson } from './lessons'
import { runTests, workspaceRead, workspaceWrite, type TestReport } from './ipc'

export type { ExerciseState } from './exerciseState'

/**
 * Getting an exercise from the bundle onto disk and back again.
 *
 * The rule that shapes all of this: the learner starts from a scaffold, never
 * from the answer. `reference.py` is written into the workspace alongside
 * everything else, because hiding a file the learner could open anyway would be
 * theatre, but the editor only ever opens `solution.py`, and revealing the
 * reference is a deliberate, recorded action.
 */

/**
 * Everything the build shipped for this exercise, except the learner's own file.
 *
 * Derived rather than listed. A hardcoded set of names was correct for as long
 * as every exercise shipped the same four files, and it would have gone wrong
 * silently the first time one shipped a fixture: the build would put the file in
 * the bundle, this would not write it, and `python3 test.py` would fail on a
 * missing file with nothing in the app explaining why. Shipping and writing are
 * now the same list by construction.
 *
 * `solution.py` is excluded because it is the one file the learner owns. The
 * bundle has no reason to contain one, and the guard is here so that a mistake
 * upstream cannot become this app overwriting their work.
 */
function managedFiles(files: Record<string, string>): string[] {
  return Object.keys(files).filter((name) => name !== SOLUTION_FILE)
}

/**
 * Records which build of the exercise the workspace was last written from.
 *
 * A dotfile so it sits out of the way in a directory the learner reads, and so
 * `python3 test.py` never picks it up. Written on every open, including the
 * first.
 */
const STAMP_FILE = '.exercise-version'

export interface PreparedExercise {
  /** Directory inside the workspace holding every file. */
  dir: string
  /** The learner's current code, restored from disk or seeded from the scaffold. */
  code: string
  /** Untouched starting point, for the reset button. */
  scaffold: string
  /** The worked solution. Held in memory; shown only when asked for. */
  reference: string
  testFile: string
  /**
   * What each test is checking, when this exercise has been mapped. Carried on
   * the prepared exercise so the results panel does not have to load the
   * compiled lesson a second time.
   */
  cases?: Record<string, { condition: string; hints: string[]; concept?: string }>
  /**
   * How the work on disk relates to the exercise that was just written over it.
   *
   * This replaced a `fresh` boolean. Two fields where `state === 'fresh'` and
   * `fresh` could disagree is one field too many, and the boolean could not say
   * the thing worth saying anyway.
   */
  state: ExerciseState
}

export class ExerciseUnavailableError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ExerciseUnavailableError'
  }
}

/** The stamp from a previous open, or undefined if there is not one to read. */
async function readStamp(dir: string): Promise<string | undefined> {
  try {
    return (await workspaceRead(`${dir}/${STAMP_FILE}`)).trim()
  } catch {
    return undefined
  }
}

/**
 * Materialize an exercise into the workspace and return what the editor needs.
 *
 * Support files are overwritten every time, so a content update reaches a
 * learner who already opened the exercise. `solution.py` is written only when
 * it does not already exist, because overwriting it would throw away their work.
 *
 * Those two rules are both right and together they leave a hole: a rewritten
 * exercise lands on top of a solution written against the old one. Reading the
 * stamp before the refresh is what closes it, and the only thing this function
 * does about it is say so. Deciding what to keep stays the learner's.
 */
export async function prepareExercise(ref: LessonRef): Promise<PreparedExercise> {
  const spec = ref.lesson.exercise
  const dir = exerciseDir(ref)
  if (!spec || !dir) {
    throw new ExerciseUnavailableError('This lesson has no exercise.')
  }

  const lesson = await loadLesson(ref.lesson.id)
  const files = lesson?.exerciseFiles
  if (!files) {
    throw new ExerciseUnavailableError(
      `The files for ${spec.id} are missing from this build. ` +
        'Run `pnpm --filter @atlas/learning build` and restart the app.',
    )
  }

  const scaffold = files[spec.scaffold]
  const reference = files[spec.reference]
  if (scaffold === undefined) {
    throw new ExerciseUnavailableError(`${spec.scaffold} is missing from this build.`)
  }

  // Read before writing anything. Once the support files are refreshed there is
  // no longer any evidence on disk of which build they replaced.
  const previousStamp = await readStamp(dir)

  // Refresh support files. If the learner has been editing the test to make it
  // pass, this quietly puts it back, which is the correct outcome.
  for (const name of managedFiles(files)) {
    await workspaceWrite(`${dir}/${name}`, files[name]!)
  }

  const hash = lesson?.exerciseHash
  let code: string
  let hasSolution: boolean
  try {
    code = await workspaceRead(`${dir}/${SOLUTION_FILE}`)
    hasSolution = true
  } catch {
    // No solution file yet. Seed it from the scaffold, which is the only time
    // this app ever writes over the learner's working file.
    code = scaffold
    await workspaceWrite(`${dir}/${SOLUTION_FILE}`, scaffold)
    hasSolution = false
  }

  const state: ExerciseState = exerciseState({
    hasSolution,
    previousStamp,
    currentHash: hash,
  })

  // Stamp after the refresh, so the state above describes what the learner is
  // being told about and the next open compares against what is now on disk.
  // Writing it even when nothing moved is what makes the next open's answer
  // trustworthy rather than another `unknown`.
  if (hash !== undefined) {
    await workspaceWrite(`${dir}/${STAMP_FILE}`, `${hash}\n`)
  }

  return {
    dir,
    code,
    scaffold,
    reference: reference ?? '',
    testFile: spec.test,
    cases: lesson?.exerciseCases,
    state,
  }
}

/** Persist the editor buffer. Called on a debounce while typing. */
export function saveSolution(dir: string, code: string): Promise<void> {
  return workspaceWrite(`${dir}/${SOLUTION_FILE}`, code)
}

/**
 * Write the buffer, then run the tests.
 *
 * Saving first is what makes the verdict trustworthy: running the previous save
 * against the current editor contents produces results that do not match what
 * the learner is looking at.
 */
export async function checkExercise(
  prepared: PreparedExercise,
  code: string,
): Promise<TestReport> {
  await saveSolution(prepared.dir, code)
  return runTests(prepared.dir, prepared.testFile, 'python')
}

/** A one-line summary for the status bar. */
export function summarize(report: TestReport): string {
  if (report.runnerError) return report.runnerError
  if (report.testsTotal === 0) return report.passed ? 'Passed' : 'Failed'
  return `${report.testsPassed} of ${report.testsTotal} tests passing`
}
