'use client'

import type { ChoiceChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { Mark, sheet } from './chrome'

/**
 * One right answer, or several.
 *
 * The notes stay hidden until the challenge is settled. A note says why an
 * option is what it is, so showing it the moment somebody clicks would answer
 * the question for them; `checkChoice` already hands the note of their first
 * pick to the runner when they are wrong, which is the same teaching at the
 * point they have earned it.
 */
export const Choice: ChallengeRenderer<ChoiceChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
}) => {
  const selected = Array.isArray(answer) ? (answer as string[]) : []

  const toggle = (id: string) => {
    if (!challenge.multiple) {
      onAnswer([id])
      return
    }
    onAnswer(selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id])
  }

  return (
    <fieldset disabled={settled}>
      <legend className="sr-only">{challenge.prompt}</legend>

      <ul className={sheet}>
        {challenge.options.map((option) => {
          const picked = selected.includes(option.id)
          return (
            <li key={option.id}>
              <label
                className={cn(
                  'flex min-h-11 cursor-pointer items-start gap-3 px-4 py-3 transition-colors duration-200 ease-paper',
                  picked ? 'bg-accent-wash' : 'hover:bg-paper-raised',
                  settled && 'cursor-default',
                )}
              >
                <input
                  type={challenge.multiple ? 'checkbox' : 'radio'}
                  name={challenge.id}
                  value={option.id}
                  checked={picked}
                  onChange={() => toggle(option.id)}
                  className="mt-1 size-4 shrink-0 accent-accent"
                />

                <span className="min-w-0">
                  <span className="block text-caption text-ink">{option.label}</span>

                  {settled && (
                    <span className="mt-2 block text-caption text-ink-soft">
                      <Mark tone={option.correct ? 'pass' : 'quiet'} className="mr-2">
                        {option.correct ? 'correct' : 'not this one'}
                      </Mark>
                      {option.note}
                    </span>
                  )}
                </span>
              </label>
            </li>
          )
        })}
      </ul>

      {challenge.multiple && !settled && (
        <p className="mt-3 font-mono text-eyebrow uppercase text-muted">More than one may be right</p>
      )}
    </fieldset>
  )
}
