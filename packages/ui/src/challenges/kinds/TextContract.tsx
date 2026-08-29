'use client'

import type { TextContractChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { quietButton } from './chrome'

/**
 * Edit a buffer until it satisfies a chain of rules.
 *
 * The most-used kind in the catalogue, so it is the plainest thing on the page:
 * a monospace field, the language it is written in, and a way back to where it
 * started. No line numbers, no highlighting, nothing that has to be kept in
 * step with a parser the platform does not run.
 */
export const TextContract: ChallengeRenderer<TextContractChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  const buffer = typeof answer === 'string' ? answer : challenge.initial
  const untouched = buffer === challenge.initial

  // Grows with the work up to a point, so a short contract is not surrounded by
  // empty field and a long one is not read through a slot.
  const rows = Math.min(22, Math.max(8, buffer.split('\n').length + 1))

  const id = `${challenge.id}-buffer`

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <label htmlFor={id} className="font-mono text-eyebrow uppercase text-muted">
          {challenge.lang}
        </label>

        <button
          type="button"
          onClick={() => onAnswer(challenge.initial)}
          disabled={settled || untouched}
          className={cn(quietButton, 'px-3')}
        >
          Start over
        </button>
      </div>

      <textarea
        id={id}
        value={buffer}
        rows={rows}
        disabled={settled}
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        onChange={(event) => onAnswer(event.target.value)}
        className="mt-2 block w-full resize-y rounded-sheet border border-rule-strong bg-paper-raised p-4 font-mono text-caption leading-relaxed text-ink transition-colors duration-200 ease-paper hover:border-accent disabled:border-rule disabled:text-ink-soft"
      />

      <p className="mt-2 font-mono text-eyebrow uppercase text-muted">
        {buffer.length} characters, checked against {challenge.rules.length}{' '}
        {challenge.rules.length === 1 ? 'rule' : 'rules'}
      </p>
    </div>
  )
}
