'use client'

import type { AssignChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { field, Mark, sheet } from './chrome'

/**
 * Sort the items into buckets.
 *
 * A select per item rather than click-item-then-click-bucket. Both are
 * reachable from a keyboard, but a native select already knows how to open on
 * a phone, announce its options, and say which one is chosen, and none of that
 * has to be rebuilt or kept working.
 */
export const Assign: ChallengeRenderer<AssignChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
  verdict,
}) => {
  const placed = (answer ?? {}) as Record<string, string>
  const complete = challenge.items.every((item) => placed[item.id])

  // `checkAssign` complains about unsorted items before it complains about
  // misplaced ones, so marking a wrong item while any are still empty would
  // point at something the banner is not talking about.
  const wrong =
    verdict && !verdict.passed && complete
      ? challenge.items.find((item) => placed[item.id] !== item.bucket)
      : undefined

  return (
    <div>
      <dl className="flex flex-wrap gap-x-8 gap-y-3 border-b border-rule pb-4">
        {challenge.buckets.map((bucket) => (
          <div key={bucket.id} className="max-w-xs">
            <dt className="font-mono text-eyebrow uppercase text-muted">{bucket.label}</dt>
            {bucket.note && <dd className="mt-1 text-caption text-ink-soft">{bucket.note}</dd>}
          </div>
        ))}
      </dl>

      <ul className={cn(sheet, 'mt-5')}>
        {challenge.items.map((item) => {
          const id = `${challenge.id}-${item.id}`
          return (
            <li
              key={item.id}
              className={cn(
                'flex min-h-11 flex-wrap items-center justify-between gap-3 px-4 py-2',
                wrong?.id === item.id && 'bg-fail-wash',
              )}
            >
              <label htmlFor={id} className="min-w-0 grow text-caption text-ink">
                {item.label}
              </label>

              {wrong?.id === item.id && <Mark tone="fail">wrong bucket</Mark>}

              <select
                id={id}
                value={placed[item.id] ?? ''}
                disabled={settled}
                onChange={(event) => onAnswer({ ...placed, [item.id]: event.target.value })}
                className={cn(field, 'shrink-0')}
              >
                <option value="">Choose</option>
                {challenge.buckets.map((bucket) => (
                  <option key={bucket.id} value={bucket.id}>
                    {bucket.label}
                  </option>
                ))}
              </select>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
