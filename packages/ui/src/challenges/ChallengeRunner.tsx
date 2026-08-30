'use client'

import { useCallback, useState } from 'react'
import {
  checkChallenge,
  machineStart,
  type Challenge,
  type CompiledChallengeSet,
  type Verdict,
} from '@atlas/core'

import { RuleMeter, WaxSeal } from '../game/marks'
import { cn } from '../lib/cn'
import { KindRenderers } from './registry'
import { useReveal } from './useReveal'

export interface ChallengeAttempt {
  challengeId: string
  passed: boolean
  attempts: number
  hintsUsed: number
}

export interface ChallengeRunnerProps {
  set: CompiledChallengeSet
  /** Fired the first time each challenge is solved. */
  onChallengePassed?: (attempt: ChallengeAttempt) => void
  /** Fired once the whole sequence is done. */
  onComplete?: () => void
  /** The two ways out, offered at the end. */
  onGoToCode?: () => void
  onGoToRead?: () => void
  hasExercise?: boolean
  /**
   * Whether the learner has already read the lesson before reaching this.
   *
   * Injected by the stage controller. It decides whether the finish offers the
   * prose as the thing to do next or as somewhere to go back to, because
   * "read the notes" is an odd thing to suggest to somebody who just did.
   */
  readingLeads?: boolean
  className?: string
}

/**
 * Stage 1: three or four challenges, in order.
 *
 * Every challenge in the catalogue runs through this, which is the point. A
 * renderer collects an answer and nothing else; the verdict banner, the hints,
 * the pacing and the way out all live here, so a new challenge kind cannot
 * invent its own idea of what passing looks like.
 *
 * Momentum is deliberately quiet. `DESIGN.md` allows three entrances on one
 * curve and says no bounce and no elastic, ever, so there is no confetti and
 * nothing springs. What carries it is pace: an immediate verdict, a seal that
 * fills, a rule that draws across as the sequence advances. The seals and the
 * meter are the components the game already shipped and no lesson had used.
 */
export function ChallengeRunner({
  set,
  onChallengePassed,
  onComplete,
  onGoToCode,
  onGoToRead,
  hasExercise = false,
  readingLeads = false,
  className,
}: ChallengeRunnerProps) {
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, unknown>>({})
  const [verdicts, setVerdicts] = useState<Record<string, Verdict | null>>({})
  const [attempts, setAttempts] = useState<Record<string, number>>({})
  const [hintsShown, setHintsShown] = useState<Record<string, number>>({})
  const [passed, setPassed] = useState<string[]>([])

  const total = set.steps.length
  const done = passed.length === total
  const current = set.steps[Math.min(index, total - 1)]!
  const currentVerdict = verdicts[current.id] ?? null
  const isSettled = passed.includes(current.id)

  const answerFor = useCallback(
    (step: Challenge) => {
      if (step.id in answers) return answers[step.id]
      return defaultAnswer(step)
    },
    [answers],
  )

  const check = useCallback(() => {
    const answer = answerFor(current)
    const verdict =
      current.kind === 'custom'
        ? (verdicts[current.id] ?? { passed: false, message: 'Work through it above.' })
        : checkChallenge(current, answer)

    settle(verdict)
  }, [answerFor, current, verdicts])

  const settle = useCallback(
    (verdict: Verdict) => {
      const tries = (attempts[current.id] ?? 0) + 1
      setAttempts((previous) => ({ ...previous, [current.id]: tries }))
      setVerdicts((previous) => ({ ...previous, [current.id]: verdict }))

      if (!verdict.passed) return
      if (passed.includes(current.id)) return

      const next = [...passed, current.id]
      setPassed(next)
      onChallengePassed?.({
        challengeId: current.id,
        passed: true,
        attempts: tries,
        hintsUsed: hintsShown[current.id] ?? 0,
      })
      if (next.length === total) onComplete?.()
    },
    [attempts, current.id, hintsShown, onChallengePassed, onComplete, passed, total],
  )

  const advance = useCallback(() => setIndex((n) => Math.min(n + 1, total - 1)), [total])

  // One hint per failed attempt, and the last one is always reachable. A
  // challenge nobody can get past ends the lesson, so hints never run out
  // before the answer does.
  const attemptsMade = attempts[current.id] ?? 0
  const earnedHints = Math.min(attemptsMade, current.hints.length)
  const shown = hintsShown[current.id] ?? 0

  const Renderer = KindRenderers[current.kind]

  return (
    <div className={cn('not-prose w-full font-sans', className)}>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-4">
        <div className="flex items-center gap-2">
          {set.steps.map((step) => (
            <WaxSeal
              key={step.id}
              earned={passed.includes(step.id)}
              title={passed.includes(step.id) ? `${step.id}, done` : step.id}
              className={cn(
                'transition-opacity duration-200 ease-paper',
                passed.includes(step.id) ? 'opacity-100' : 'opacity-35',
              )}
            />
          ))}
        </div>
        <p className="font-mono text-eyebrow uppercase text-muted">
          {done ? 'Complete' : `${index + 1} of ${total}`}
        </p>
      </header>

      <RuleMeter className="mt-0" fraction={passed.length / total} label="Stage 1 progress" />

      <p className="mt-5 text-lead font-serif text-ink-soft">{set.goal}</p>

      {done ? (
        <Finished
          hasExercise={hasExercise}
          onGoToCode={onGoToCode}
          onGoToRead={onGoToRead}
          readingLeads={readingLeads}
          steps={set.steps}
        />
      ) : (
        <section key={current.id} className="mt-6">
          <h3 className="text-section font-serif text-ink">{current.prompt}</h3>

          {current.context && <Context context={current.context} />}

          <div className="mt-5">
            {Renderer ? (
              <Renderer
                challenge={current as never}
                answer={answerFor(current)}
                onAnswer={(answer) =>
                  setAnswers((previous) => ({ ...previous, [current.id]: answer }))
                }
                onVerdict={settle}
                verdict={currentVerdict}
                settled={isSettled}
              />
            ) : (
              <p className="text-caption text-warn">
                This challenge needs a newer version of the app.
              </p>
            )}
          </div>

          {currentVerdict && <Banner verdict={currentVerdict} reveal={isSettled ? current.reveal : undefined} />}

          {shown > 0 && (
            <ul className="mt-4 space-y-2 border-l-2 border-rule-strong pl-4 text-caption text-ink-soft">
              {current.hints.slice(0, shown).map((hint, position) => (
                <li key={position} className="animate-fade-in">
                  {hint}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-rule pt-5">
            {!isSettled && current.kind !== 'custom' && (
              <button
                type="button"
                onClick={check}
                className="inline-flex min-h-11 items-center rounded-field bg-accent px-6 text-caption font-medium text-white transition-colors duration-200 ease-paper hover:bg-accent-deep active:bg-accent-deep"
              >
                Check
              </button>
            )}

            {isSettled && (
              <button
                type="button"
                onClick={() => (index + 1 < total ? advance() : undefined)}
                className="inline-flex min-h-11 items-center rounded-field bg-accent px-6 text-caption font-medium text-white transition-colors duration-200 ease-paper hover:bg-accent-deep"
              >
                {index + 1 < total ? 'Next' : 'Finish'}
              </button>
            )}

            {/*
              No hint before the first attempt: the challenge is meant to be
              tried, and offering help beside a puzzle nobody has read yet is
              what turns it into a walkthrough. Nothing here once it is solved
              either, because a hint for something already done is clutter.
            */}
            {!isSettled && attemptsMade > 0 && shown < current.hints.length && (
              <button
                type="button"
                onClick={() =>
                  shown < earnedHints &&
                  setHintsShown((previous) => ({ ...previous, [current.id]: shown + 1 }))
                }
                className={cn(
                  'min-h-11 font-mono text-caption transition-colors duration-200 ease-paper',
                  shown < earnedHints ? 'text-accent hover:text-accent-deep' : 'text-muted',
                )}
              >
                {shown < earnedHints ? (shown === 0 ? 'Hint' : 'Another hint') : 'Try once more first'}
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

/** What the runner starts a challenge with, before the learner touches it. */
function defaultAnswer(step: Challenge): unknown {
  switch (step.kind) {
    case 'text-contract':
      return step.initial
    case 'order':
      // Rotated rather than shuffled, so a reload does not reorder the board
      // under somebody mid-thought and the start is never the answer.
      return step.items.map((item) => item.id).slice(1).concat(step.items[0]!.id)
    case 'tune':
      return Object.fromEntries(step.inputs.map((input) => [input.id, input.initial]))
    case 'machine':
      return machineStart(step)
    case 'assign':
      return {}
    case 'blanks':
      return {}
    case 'numeric':
      return Number.NaN
    default:
      return []
  }
}

function Banner({ verdict, reveal }: { verdict: Verdict; reveal?: string }) {
  const ref = useReveal<HTMLDivElement>()

  return (
    <div
      ref={ref}
      data-reveal="fade"
      role="status"
      aria-live="polite"
      className={cn(
        'mt-5 rounded-field border-l-2 px-4 py-3 text-caption',
        verdict.passed ? 'border-pass bg-pass-wash text-ink' : 'border-fail bg-fail-wash text-ink',
      )}
    >
      {verdict.passed ? (
        <p className="font-medium text-pass">That works.</p>
      ) : (
        <p>{verdict.message}</p>
      )}
      {verdict.detail && <p className="mt-1 font-mono text-[12px] text-muted">{verdict.detail}</p>}
      {reveal && <p className="mt-2 text-ink-soft">{reveal}</p>}
    </div>
  )
}

function Finished({
  steps,
  hasExercise,
  onGoToCode,
  onGoToRead,
  readingLeads,
}: {
  steps: Challenge[]
  hasExercise: boolean
  onGoToCode?: () => void
  onGoToRead?: () => void
  readingLeads: boolean
}) {
  const ref = useReveal<HTMLDivElement>()

  return (
    <div ref={ref} data-reveal="settle" className="mt-8">
      <p className="text-lead font-serif text-ink">
        {readingLeads
          ? `You put ${steps.length} things from the lesson to work.`
          : `You worked out ${steps.length} things about this that you were not told.`}
      </p>

      <div className="mt-7 grid gap-4 sm:grid-cols-2">
        {hasExercise && onGoToCode && (
          <button
            type="button"
            onClick={onGoToCode}
            className="rounded-sheet border border-accent bg-accent-wash p-5 text-left transition-colors duration-200 ease-paper hover:bg-accent/10"
          >
            <span className="font-mono text-eyebrow uppercase text-accent">Next</span>
            <span className="mt-1 block font-serif text-section text-ink">Write the code</span>
            <span className="mt-2 block text-caption text-ink-soft">
              The same ideas, in a file that has to pass its tests.
            </span>
          </button>
        )}

        {onGoToRead && (
          <button
            type="button"
            onClick={onGoToRead}
            className="rounded-sheet border border-rule-strong bg-paper p-5 text-left transition-colors duration-200 ease-paper hover:bg-paper-sunken"
          >
            <span className="font-mono text-eyebrow uppercase text-muted">
              {readingLeads ? 'Back' : 'Optional'}
            </span>
            <span className="mt-1 block font-serif text-section text-ink">
              {readingLeads ? 'Reread the notes' : 'Read the notes'}
            </span>
            <span className="mt-2 block text-caption text-ink-soft">
              The edge cases, the tradeoffs, and where this breaks in production.
            </span>
          </button>
        )}
      </div>
    </div>
  )
}

function Context({ context }: { context: NonNullable<Challenge['context']> }) {
  switch (context.as) {
    case 'prose':
      return <p className="mt-4 text-caption text-ink-soft">{context.text}</p>
    case 'code':
      return (
        <pre className="mt-4 overflow-x-auto rounded-sheet bg-paper-sunken p-4 font-mono text-[13px] leading-relaxed text-ink">
          <code>{context.source}</code>
        </pre>
      )
    case 'log':
      return (
        <pre className="mt-4 overflow-x-auto rounded-sheet bg-paper-sunken p-4 font-mono text-[12px] leading-relaxed text-ink-soft">
          {context.lines.join('\n')}
        </pre>
      )
    case 'pairs':
      return (
        <dl className="mt-4 divide-y divide-rule rounded-sheet border border-rule">
          {context.items.map((item) => (
            <div key={item.k} className="flex gap-4 px-4 py-2 text-caption">
              <dt className="w-40 shrink-0 font-mono text-muted">{item.k}</dt>
              <dd className="text-ink-soft">{item.v}</dd>
            </div>
          ))}
        </dl>
      )
    case 'table':
      return (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-caption">
            {context.caption && (
              <caption className="pb-2 text-left text-muted">{context.caption}</caption>
            )}
            <thead>
              <tr>
                {context.columns.map((column) => (
                  <th key={column} className="border-b border-rule-strong px-3 py-2 text-left font-mono text-muted">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {context.rows.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, position) => (
                    <td key={position} className="border-b border-rule px-3 py-2 font-mono text-ink-soft">
                      {String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
  }
}
