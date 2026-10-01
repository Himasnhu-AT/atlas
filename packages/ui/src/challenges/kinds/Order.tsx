'use client'

import { useEffect, useRef, useState } from 'react'
import type { OrderChallenge } from '@atlas/core'

import { cn } from '../../lib/cn'
import type { ChallengeRenderer } from '../protocol'
import { Mark, sheet } from './chrome'

/**
 * Put the steps in order.
 *
 * Up and down buttons rather than HTML5 drag and drop. `MemoryLayoutVisualizer`
 * made that call first and it is the right one: dragging is unreachable from a
 * keyboard, unreliable under a screen reader, and on a touch screen it fights
 * the scroll gesture that a learner is using to read the list.
 */
export const Order: ChallengeRenderer<OrderChallenge> = ({
  challenge,
  answer,
  onAnswer,
  settled,
  verdict,
}) => {
  const order = Array.isArray(answer) ? (answer as string[]) : []
  const labels = new Map(challenge.items.map((item) => [item.id, item.label]))

  const buttons = useRef(new Map<string, HTMLButtonElement | null>())
  const [moved, setMoved] = useState<{ id: string; direction: 'up' | 'down' } | null>(null)

  // A row that moves takes its buttons with it, so the focus ring would be left
  // pointing at whichever row slid into that place. Put it back on the row the
  // learner is actually working with, falling the other way when the one they
  // pressed has just become the end of the list.
  useEffect(() => {
    if (!moved) return
    const asked = buttons.current.get(`${moved.id}:${moved.direction}`)
    const other = buttons.current.get(`${moved.id}:${moved.direction === 'up' ? 'down' : 'up'}`)
    ;(asked && !asked.disabled ? asked : other)?.focus()
    setMoved(null)
  }, [moved])

  const move = (index: number, direction: 'up' | 'down') => {
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= order.length) return

    const next = [...order]
    next[index] = order[target]!
    next[target] = order[index]!
    onAnswer(next)
    setMoved({ id: order[index]!, direction })
  }

  // Marks the earliest row that has to move. This decides nothing: the runner
  // has already checked the attempt and this is the same position `checkOrder`
  // named in the message the banner is showing.
  const firstWrong =
    verdict && !verdict.passed
      ? challenge.solution.findIndex((id, index) => order[index] !== id)
      : -1

  return (
    <ol className={sheet}>
      {order.map((id, index) => (
        <li
          key={id}
          className={cn(
            'flex min-h-11 items-center gap-3 px-4 py-2',
            index === firstWrong && 'bg-fail-wash',
          )}
        >
          <span aria-hidden="true" className="w-5 shrink-0 font-mono text-caption text-muted">
            {index + 1}
          </span>

          <span className="min-w-0 grow text-caption text-ink">{labels.get(id) ?? id}</span>

          {index === firstWrong && <Mark tone="fail">move this</Mark>}

          <span className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              ref={(node) => {
                buttons.current.set(`${id}:up`, node)
              }}
              onClick={() => move(index, 'up')}
              disabled={settled || index === 0}
              className="inline-flex size-11 items-center justify-center rounded-field border border-rule text-ink-soft transition-colors duration-200 ease-paper hover:bg-paper-sunken disabled:border-transparent disabled:text-muted"
            >
              <span aria-hidden="true">&uarr;</span>
              <span className="sr-only">Move {labels.get(id) ?? id} up</span>
            </button>

            <button
              type="button"
              ref={(node) => {
                buttons.current.set(`${id}:down`, node)
              }}
              onClick={() => move(index, 'down')}
              disabled={settled || index === order.length - 1}
              className="inline-flex size-11 items-center justify-center rounded-field border border-rule text-ink-soft transition-colors duration-200 ease-paper hover:bg-paper-sunken disabled:border-transparent disabled:text-muted"
            >
              <span aria-hidden="true">&darr;</span>
              <span className="sr-only">Move {labels.get(id) ?? id} down</span>
            </button>
          </span>
        </li>
      ))}
    </ol>
  )
}
