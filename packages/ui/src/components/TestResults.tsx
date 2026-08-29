'use client'

import { useState } from 'react'
import {
  humaniseTestId,
  unmetTests,
  type RunOutcome,
  type TestOutcome,
} from '@atlas/core'

import { cn } from '../lib/cn'

/**
 * One test's authored meaning. Structurally the `ExerciseCase` the content
 * build validates, declared here rather than imported so that this package
 * does not take a dependency on the content package for one shape.
 */
export interface CaseNote {
  condition: string
  hints: string[]
  concept?: string
}

export interface TestResultsProps {
  outcome: RunOutcome
  /** Keyed on `ClassName.test_method`. Absent until an exercise has a map. */
  cases?: Record<string, CaseNote>
  /** The raw runner text, for anyone who wants the traceback. */
  output?: string
  /**
   * How many times this learner has run this exercise, this run included.
   * Hints escalate with it, so a first run offers one and a fifth offers all
   * three. Struggling earns the help; the first run does not hand it over.
   */
  attemptNumber: number
  /** Web passes a router push, desktop passes its own navigate. */
  onOpenConcept?: (conceptId: string) => void
  className?: string
}

/**
 * What a test run meant, in the learner's terms.
 *
 * Both apps render this. The web used to print the last four kilobytes of
 * unittest output into a `<pre>`; the desktop showed one line reading "3 of 15
 * tests passing" and never displayed the output at all. Neither told anybody
 * which case they had missed, which is the only thing they did not already
 * know.
 */
export function TestResults({
  outcome,
  cases,
  output,
  attemptNumber,
  onOpenConcept,
  className,
}: TestResultsProps) {
  const unmet = unmetTests(outcome)
  const passed =
    outcome.kind === 'tests' && outcome.testsTotal > 0 && outcome.testsPassed === outcome.testsTotal

  return (
    <div className={cn('not-prose font-sans text-caption', className)}>
      <Headline outcome={outcome} passed={passed} />

      {outcome.kind === 'load_error' && outcome.loadError && (
        <p className="mt-3 rounded-field border-l-2 border-fail bg-fail-wash px-4 py-3 font-mono text-ink">
          {outcome.loadError.exception}: {outcome.loadError.message}
          {outcome.loadError.file && (
            <span className="text-muted">
              {' '}
              &middot; {outcome.loadError.file}
              {outcome.loadError.line ? `:${outcome.loadError.line}` : ''}
            </span>
          )}
        </p>
      )}

      {outcome.kind === 'tests' && unmet.length > 0 && (
        <ul className="mt-4 space-y-2">
          {unmet.map((test) => (
            <Row
              key={test.id}
              test={test}
              note={cases?.[test.id]}
              attemptNumber={attemptNumber}
              onOpenConcept={onOpenConcept}
            />
          ))}
        </ul>
      )}

      {outcome.truncated && (
        <p className="mt-3 text-muted">
          Only the first results are listed. Run again once you have fewer failing.
        </p>
      )}

      {output && output.trim().length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-muted transition-colors hover:text-ink">
            Show what the tests printed
          </summary>
          <pre className="mt-2 max-h-80 overflow-auto rounded-field bg-paper-sunken p-3 font-mono text-[12px] leading-relaxed text-ink-soft">
            {output}
          </pre>
        </details>
      )}
    </div>
  )
}

function Headline({ outcome, passed }: { outcome: RunOutcome; passed: boolean }) {
  // A syntax error is one mistake, not every condition failing, so it never
  // gets a denominator. Showing "0 of 44" to somebody who left out a colon
  // describes a catastrophe that did not happen.
  const text =
    outcome.kind === 'load_error'
      ? 'Python could not read your file'
      : outcome.kind === 'crashed'
        ? 'The tests stopped before they finished'
        : passed
          ? 'Every condition met'
          : `${outcome.testsPassed} of ${outcome.testsTotal} conditions met`

  return (
    <p
      role="status"
      aria-live="polite"
      className={cn(
        'font-mono font-medium',
        passed ? 'text-pass' : outcome.kind === 'tests' ? 'text-fail' : 'text-warn',
      )}
    >
      {text}
    </p>
  )
}

function Row({
  test,
  note,
  attemptNumber,
  onOpenConcept,
}: {
  test: TestOutcome
  note?: CaseNote
  attemptNumber: number
  onOpenConcept?: (conceptId: string) => void
}) {
  const [shown, setShown] = useState(0)

  // One hint on the first run, two on the third, all three on the fifth. The
  // same bargain as the exercise timebox: struggling first, help after.
  const earned = note ? Math.min(Math.max(attemptNumber - 1, 0), note.hints.length) : 0
  const canReveal = shown < earned

  return (
    <li className="rounded-field border-l-2 border-fail bg-fail-wash px-4 py-3">
      <p className="text-ink">
        {test.status === 'not_run' ? (
          <span className="text-muted">Never checked, because the fixture could not be set up: </span>
        ) : (
          <span className="font-medium">You did not handle: </span>
        )}
        {note ? (
          note.condition
        ) : (
          // No authored map for this exercise yet. The method name is weaker,
          // because it repeats words the learner can already read, and it is
          // rendered quietly so the gap is visible to whoever authors the map.
          <span className="text-muted">{humaniseTestId(test.id)}</span>
        )}
      </p>

      {(test.exception || test.where) && (
        <p className="mt-1 font-mono text-[12px] text-muted">
          {test.exception}
          {test.where && ` · ${test.where.file}:${test.where.line}`}
          {test.message && <span className="text-ink-soft"> · {test.message}</span>}
        </p>
      )}

      {note && shown > 0 && (
        <ul className="mt-2 space-y-1 border-l border-rule-strong pl-3 text-ink-soft">
          {note.hints.slice(0, shown).map((hint, index) => (
            <li key={index} className="animate-fade-in">
              {hint}
            </li>
          ))}
        </ul>
      )}

      {note && (
        <div className="mt-2 flex items-center gap-4">
          {shown < note.hints.length && (
            <button
              type="button"
              onClick={() => canReveal && setShown((n) => n + 1)}
              className={cn(
                'font-mono text-[12px] transition-colors',
                canReveal ? 'cursor-pointer text-accent hover:text-accent-deep' : 'text-muted',
              )}
            >
              {canReveal
                ? shown === 0
                  ? 'Hint'
                  : 'Another hint'
                : 'Run it again for another hint'}
            </button>
          )}

          {note.concept && onOpenConcept && (
            <button
              type="button"
              onClick={() => onOpenConcept(note.concept!)}
              className="cursor-pointer font-mono text-[12px] text-muted transition-colors hover:text-ink"
            >
              Read about this
            </button>
          )}
        </div>
      )}
    </li>
  )
}
