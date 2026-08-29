import { z } from 'zod'

/**
 * What one test run means, in the one shape both graders produce.
 *
 * The desktop runs a real interpreter and the web runs CPython on WebAssembly,
 * and this file is the reason a verdict from either is the same object. The
 * Python that fills it in is shared too: `packages/learning/runner/atlas_report.py`
 * is compiled into the Rust binary and fetched by the browser worker. Changing
 * the shape here means changing that file, its tests, and the Rust mirror in
 * `apps/desktop/src-tauri/src/grader.rs`. There is no fourth place.
 *
 * Before this existed, both runners reduced `result.failures` and
 * `result.errors` to one integer and threw the rest away, and the desktop
 * recovered its counts by string-scraping unittest's summary. A learner was
 * told "3 of 15 tests passing" and never which condition they had missed.
 */

/**
 * Sized for the largest suite in the catalogue with room, not for the mean.
 * `memory-window` has 44 tests; the mean is 17.5.
 */
export const MAX_REPORTED_TESTS = 120
export const MAX_TEST_ID_CHARS = 120
export const MAX_MESSAGE_CHARS = 300

/**
 * Ids only, and fewer than the runtime keeps. The wire is not the UI: what an
 * aggregate wants from an attempt is which condition was missed, and
 * `stdoutTail` already carries a readable log for anyone debugging one.
 */
export const MAX_PERSISTED_FAILED_TESTS = 60

export const TestStatus = z.enum(['passed', 'failed', 'error', 'skipped', 'not_run'])
export type TestStatus = z.infer<typeof TestStatus>

export const TestFrame = z.object({
  file: z.string().max(120),
  line: z.number().int().nonnegative(),
})
export type TestFrame = z.infer<typeof TestFrame>

export const TestOutcome = z.object({
  /**
   * `ClassName.test_method`, normalised, and the key an exercise's case map is
   * written against. Not `test.ClassName.test_method`: the module is always the
   * exercise's own test file, so the prefix carries nothing.
   *
   * A `subTest` collapses to one record rather than one per parameter set. The
   * learner missed one condition, not four.
   */
  id: z.string().max(MAX_TEST_ID_CHARS),
  status: TestStatus,
  durationMs: z.number().int().nonnegative().optional(),
  /** `AssertionError`, `KeyError`. Absent for a pass. */
  exception: z.string().max(80).optional(),
  /**
   * `str(exception)`, truncated. That is the assertion message, including the
   * custom third argument when a test carries one. Deliberately not the
   * traceback: a traceback is what the raw output is for.
   */
  message: z.string().max(MAX_MESSAGE_CHARS).optional(),
  /** Deepest frame in a file the learner owns or can read. */
  where: TestFrame.optional(),
})
export type TestOutcome = z.infer<typeof TestOutcome>

export const RunKind = z.enum([
  /** The suite loaded and ran. The only kind with a meaningful denominator. */
  'tests',
  /** The suite could not be imported. A syntax error, usually. Nothing ran. */
  'load_error',
  /** The process died without writing a report. `os._exit`, a segfault, a kill. */
  'crashed',
])
export type RunKind = z.infer<typeof RunKind>

export const RunLoadError = z.object({
  exception: z.string().max(80),
  message: z.string().max(MAX_MESSAGE_CHARS),
  file: z.string().max(120).optional(),
  line: z.number().int().nonnegative().optional(),
})
export type RunLoadError = z.infer<typeof RunLoadError>

export const RunOutcome = z.object({
  kind: RunKind,
  /**
   * How many tests the loader found, not `result.testsRun`.
   *
   * They differ exactly when `setUpClass` raises: unittest never runs that
   * class's tests, `testsRun` shrinks, and "3 of 4 passing" becomes a lie about
   * a suite of 44. The loaded count is the honest denominator, and the tests
   * that never got there are reported as `not_run`.
   */
  testsTotal: z.number().int().nonnegative(),
  testsPassed: z.number().int().nonnegative(),
  tests: z.array(TestOutcome).max(MAX_REPORTED_TESTS),
  /** True when the suite had more tests than `MAX_REPORTED_TESTS`. */
  truncated: z.boolean(),
  /** Present only when `kind` is `load_error`. */
  loadError: RunLoadError.optional(),
})
export type RunOutcome = z.infer<typeof RunOutcome>

/**
 * A run that produced no report at all.
 *
 * The old desktop scraper answered this case with `(0, 1)`, inventing a test
 * that never existed. Saying nothing ran is both true and more useful.
 */
export function crashedRun(): RunOutcome {
  return { kind: 'crashed', testsTotal: 0, testsPassed: 0, tests: [], truncated: false }
}

/** The tests a learner has not satisfied, in the order the suite declares them. */
export function unmetTests(outcome: RunOutcome): TestOutcome[] {
  return outcome.tests.filter((test) => test.status !== 'passed' && test.status !== 'skipped')
}

/**
 * A readable stand-in for an exercise with no authored case map yet.
 *
 * `test_ignores_braces_inside_strings` becomes "ignores braces inside strings".
 * Weaker than an authored condition, and deliberately so: it repeats words the
 * learner has already seen in a name they can read themselves. It exists so
 * that the 100 exercises without a map still say something, and so that the
 * gap is visible rather than blank.
 */
export function humaniseTestId(id: string): string {
  const method = id.includes('.') ? id.slice(id.lastIndexOf('.') + 1) : id
  const words = method.replace(/^test_/, '').replace(/_/g, ' ').trim()
  return words.length === 0 ? id : words
}
