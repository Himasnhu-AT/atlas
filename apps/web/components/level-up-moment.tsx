'use client'

import { type LevelProgress, romanFor } from '@atlas/core'
import { LevelUp } from '@atlas/ui/game'
import { useEffect, useRef, useState } from 'react'

/**
 * Shows a level-up, using the page's own arrival gesture, and then lets it go.
 *
 * The gesture needs help here. `[data-reveal]` is opacity 0 until something adds
 * `data-shown`, which for scrolled content is the IntersectionObserver in
 * `Reveal`. Nothing observes an element injected after a click, so it would be
 * rendered, announced to a screen reader, and never drawn. Flipping the
 * attribute on the next frame is what the observer would have done, and the rule
 * inside needs the same, because `[data-rule]` only unrolls once marked shown.
 *
 * It clears itself. A banner that stays turns the rarest event in the product
 * into furniture, and the ledger is where a rank lives permanently anyway.
 */
export function LevelUpMoment({
  levelledTo,
  onDone,
  /** Long enough to read a rank nobody has seen, short enough to be gone next lesson. */
  holdMs = 12_000,
}: {
  levelledTo: LevelProgress | null
  onDone: () => void
  holdMs?: number
}) {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!levelledTo) return
    const frame = requestAnimationFrame(() => {
      const banner = ref.current?.firstElementChild
      banner?.setAttribute('data-shown', '')
      banner?.querySelector('[data-rule]')?.setAttribute('data-shown', '')
    })
    return () => cancelAnimationFrame(frame)
  }, [levelledTo])

  useEffect(() => {
    if (!levelledTo) return
    const timer = setTimeout(onDone, holdMs)
    return () => clearTimeout(timer)
  }, [levelledTo, holdMs, onDone])

  if (!levelledTo) return null

  return (
    <div ref={ref}>
      <LevelUp
        level={levelledTo.level}
        rankName={levelledTo.rank.name}
        roman={romanFor(levelledTo.rank.tier)}
      />
    </div>
  )
}

/** The shape both XP-granting routes add to their response. */
export interface Levelled {
  levelledTo?: LevelProgress
}

/** Holds the level a click just crossed into, if it crossed one. */
export function useLevelUp() {
  const [levelledTo, setLevelledTo] = useState<LevelProgress | null>(null)
  return { levelledTo, setLevelledTo, clear: () => setLevelledTo(null) }
}
