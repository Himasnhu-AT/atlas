import Link from 'next/link'

import { BrowserExercise } from './browser-exercise'

/**
 * Closes a lesson that has an exercise.
 *
 * Not a card and not an alert. It is a ruled block, the way a textbook sets off
 * the problem at the end of a chapter, so it reads as part of the page rather
 * than as a widget dropped onto it.
 */
export function ExerciseCallout({
  exerciseId,
  timeboxMinutes,
  files,
  browser,
}: {
  exerciseId: string
  timeboxMinutes: number
  files?: Record<string, string>
  /**
   * What the content build decided about running this in a browser. Derived
   * from the exercise's own imports, so it cannot drift from the code.
   */
  browser?: { runnable: boolean; reason?: string }
}) {
  const scaffold = files?.['scaffold.py']
  const testCount = files?.['test.py']
    ? (files['test.py'].match(/def test_/g) ?? []).length
    : 0

  return (
    <section className="mt-16 border-t-2 border-ink pt-7">
      <p className="text-eyebrow font-medium uppercase text-muted">Exercise</p>

      <h2 className="mt-3 font-mono text-section text-ink">{exerciseId}</h2>

      <p className="mt-4 max-w-[58ch] text-ink-soft">
        {testCount > 0
          ? `${testCount} tests, graded on your machine in about a second. `
          : 'Graded on your machine in about a second. '}
        If you are stuck for {timeboxMinutes} minutes, the app offers the reference solution.
      </p>

      {scaffold && files && browser?.runnable ? (
        <BrowserExercise exerciseId={exerciseId} scaffold={scaffold} files={files} />
      ) : scaffold ? (
        <details className="group mt-7">
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 text-caption text-accent-deep transition-colors duration-200 ease-paper hover:text-ink">
            Preview the scaffold
            <span
              aria-hidden
              className="transition-transform duration-200 ease-paper group-open:rotate-180"
            >
              &darr;
            </span>
          </summary>
          <pre className="mt-4 max-h-96 overflow-auto rounded-sheet border border-rule bg-paper-raised p-4 text-[13px] leading-relaxed">
            <code>{scaffold}</code>
          </pre>
        </details>
      ) : null}

      {browser && !browser.runnable && (
        <p className="mt-5 max-w-[58ch] text-caption text-muted">
          This one needs the desktop app: {browser.reason}. Everything else about
          it is the same.
        </p>
      )}

      <Link
        href="/download"
        className={
          browser?.runnable
            ? 'mt-6 inline-flex min-h-11 items-center text-caption text-accent-deep transition-colors duration-200 ease-paper hover:text-ink'
            : 'mt-7 inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep'
        }
      >
        {browser?.runnable ? 'Or use the desktop app' : 'Open in the desktop app'}
      </Link>
    </section>
  )
}
