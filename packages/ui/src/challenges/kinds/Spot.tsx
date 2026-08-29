'use client'

import type { SpotChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { Mark } from './chrome'

/**
 * Find the line that causes it.
 *
 * Each line is a real button, so the listing is walked with Tab and toggled
 * with Space, and `aria-pressed` says which ones are picked without relying on
 * the tint that says it visually.
 */
export const Spot: ChallengeRenderer<SpotChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
  verdict,
}) => {
  const lines = challenge.source.replace(/\n$/, '').split('\n')
  const clicked = Array.isArray(answer) ? (answer as number[]) : []

  // The one line `checkSpot` complained about. Picks stay in click order, so
  // this is the same line the banner's decoy note is talking about.
  const stray =
    verdict && !verdict.passed
      ? clicked.find((line) => !challenge.targets.includes(line))
      : undefined

  const toggle = (index: number) => {
    onAnswer(
      clicked.includes(index) ? clicked.filter((line) => line !== index) : [...clicked, index],
    )
  }

  return (
    <div>
      <p className="font-mono text-eyebrow uppercase text-muted">
        {challenge.lang}
        {challenge.requireAll && challenge.targets.length > 1 && ', more than one line'}
      </p>

      <div className="mt-2 overflow-x-auto rounded-sheet border border-rule bg-paper-sunken py-2">
        <ol>
          {lines.map((line, index) => {
            const picked = clicked.includes(index)
            return (
              <li key={index}>
                <button
                  type="button"
                  aria-pressed={picked}
                  disabled={settled}
                  onClick={() => toggle(index)}
                  className={cn(
                    'flex min-h-11 w-full items-center gap-3 border-l-2 px-3 text-left font-mono text-caption transition-colors duration-200 ease-paper',
                    picked ? 'border-accent bg-accent-wash' : 'border-transparent',
                    !picked && !settled && 'hover:bg-paper-raised',
                    index === stray && 'border-fail bg-fail-wash',
                  )}
                >
                  <span aria-hidden="true" className="w-8 shrink-0 select-none text-right text-muted">
                    {index + 1}
                  </span>

                  <span className="grow whitespace-pre text-ink">{line || ' '}</span>

                  {picked && (
                    <Mark tone={index === stray ? 'fail' : 'quiet'} className="shrink-0">
                      {index === stray ? 'not this one' : 'picked'}
                    </Mark>
                  )}
                </button>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
