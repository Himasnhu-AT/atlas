'use client'

import { cn } from '../../lib/cn'

/**
 * The chrome every renderer needs, in one place.
 *
 * Ten kinds each restating the same field and sheet classes is ten chances for
 * them to drift, and the drift is invisible: a select 40px tall in one
 * challenge and 44px in the next looks correct on either screen alone.
 */

/** Inputs and selects. The height is the 44px floor, not padding that happens to reach it. */
export const field =
  'min-h-11 rounded-field border border-rule-strong bg-paper-raised px-3 text-caption text-ink transition-colors duration-200 ease-paper hover:border-accent disabled:border-rule disabled:text-muted'

/** The ruled container a learner works down. There are no cards. */
export const sheet = 'divide-y divide-rule rounded-sheet border border-rule bg-paper'

/** A button that is an action rather than the one thing to press next. */
export const quietButton =
  'inline-flex min-h-11 items-center rounded-field border border-rule-strong px-4 text-caption text-ink transition-colors duration-200 ease-paper hover:bg-paper-sunken disabled:border-rule disabled:text-muted'

export type MarkTone = 'pass' | 'fail' | 'quiet'

const glyph: Record<MarkTone, string> = { pass: '✓', fail: '✕', quiet: '·' }

const tint: Record<MarkTone, string> = {
  pass: 'text-pass',
  fail: 'text-fail',
  quiet: 'text-muted',
}

/**
 * A result, said in words.
 *
 * The word is not redundant with the colour. `pass` and `fail` are the only two
 * colours in the palette that mean anything, and somebody who cannot tell them
 * apart still has to be able to read the board.
 */
export function Mark({
  tone,
  children,
  className,
}: {
  tone: MarkTone
  children: React.ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-mono text-eyebrow uppercase',
        tint[tone],
        className,
      )}
    >
      <span aria-hidden="true">{glyph[tone]}</span>
      {children}
    </span>
  )
}
