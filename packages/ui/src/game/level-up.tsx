import { RankStamp } from './marks'

export interface LevelUpProps {
  level: number
  /** The rank at that level: "Wayfarer", "Cartographer". */
  rankName: string
  /** Its numeral, for the stamp. "II", "VI". */
  roman: string
  className?: string
}

/**
 * The one moment in the product that interrupts the page.
 *
 * A rule drawn across the column and a rank pressed into it, which is the same
 * two gestures the rest of the site already uses: `[data-rule]` sweeps a
 * hairline from the left, `[data-reveal]` settles what sits on it. Nothing
 * bounces and nothing bursts, and reduced motion turns both into a plain appear
 * without losing the message. DESIGN.md forbids elastic motion, and the rarest
 * event in the product is not the place to make an exception to that.
 *
 * Stateless on purpose. The caller decides when it exists and when it stops,
 * which keeps this file usable from a server component and keeps the timing in
 * one place per surface rather than hidden in here.
 */
export function LevelUp({ level, rankName, roman, className = '' }: LevelUpProps) {
  return (
    <div
      data-reveal
      // Announced, because a rank appearing at the foot of a page is the whole
      // feedback and a reader not looking at this corner would get silence.
      role="status"
      className={`mt-10 ${className}`}
    >
      <div data-rule className="h-px w-full origin-left bg-accent" aria-hidden />

      <div className="mt-5 flex items-center gap-4">
        <RankStamp roman={roman} className="shrink-0 text-accent-deep" />
        <p className="font-serif text-lede text-ink">
          Level {level}. <span className="italic text-accent-deep">{rankName}</span>
        </p>
      </div>
    </div>
  )
}
