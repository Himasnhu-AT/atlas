import Link from 'next/link'

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
}: {
  exerciseId: string
  timeboxMinutes: number
  files?: Record<string, string>
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

      {scaffold && (
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
      )}

      <Link
        href="/download"
        className="mt-7 inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
      >
        Open in the desktop app
      </Link>
    </section>
  )
}
