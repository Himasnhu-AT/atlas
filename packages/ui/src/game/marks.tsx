/**
 * The game's marks, drawn rather than illustrated.
 *
 * Every one of these is inline SVG using `currentColor` and sized in `em`, so
 * they inherit type colour and scale with the text they sit beside, print
 * correctly, and cost nothing to retheme. There are no image files and no icon
 * font: an asset that cannot take the ink colour would be the one thing on the
 * page that is not made of ink.
 *
 * The vocabulary is a workbook's, because DESIGN.md's one rule still holds. A
 * rank is a stamp pressed into the page. A finished module gets a wax seal. A
 * locked one is territory nobody has surveyed. None of it bounces.
 */

export interface MarkProps {
  className?: string
  title?: string
}

/**
 * A rank stamp: a ring, a numeral, and the deliberate unevenness of something
 * pressed by hand. The wobble is fixed rather than random, so the same rank is
 * the same shape every time a reader sees it.
 */
export function RankStamp({
  roman,
  className = '',
  title,
}: MarkProps & { roman: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={`size-[3.5em] ${className}`}
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {title && <title>{title}</title>}
      {/* Two rings, slightly out of true with each other, the way a stamp lands. */}
      <circle cx="32" cy="32" r="28.5" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
      <circle cx="31.4" cy="32.5" r="24" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.35" />
      <text
        x="32"
        y="33"
        textAnchor="middle"
        dominantBaseline="central"
        fill="currentColor"
        fontSize="19"
        fontFamily="var(--font-serif)"
        letterSpacing="0.06em"
      >
        {roman}
      </text>
    </svg>
  )
}

/**
 * A wax seal. Filled when earned, an empty impression when not.
 *
 * The unearned state is drawn rather than hidden, because a seal a learner can
 * see is a goal and one they cannot is a surprise.
 */
export function WaxSeal({ earned, className = '', title }: MarkProps & { earned: boolean }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={`size-[1.6em] ${className}`}
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {title && <title>{title}</title>}
      {/* A blob with an uneven edge, not a circle: wax does not land round. */}
      <path
        d="M16 2.6c4.4-.9 8.3 1.2 10.6 4.6 2.4 3.5 2.6 7.6 1.2 11.2-1.4 3.7-4.3 6.8-8 8.4-3.6 1.5-7.6 1.2-10.6-1-3-2.3-4.9-6-5.1-9.8-.2-3.9 1.4-7.8 4.3-10.2A11.9 11.9 0 0 1 16 2.6Z"
        fill={earned ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={earned ? 0 : 1.25}
        // An unearned seal is a goal, so it has to be legible rather than a
        // ghost. It reads as quiet because it is hollow and takes a muted ink,
        // not because it has been faded almost out of the page.
        opacity={earned ? 0.92 : 0.7}
      />
      {earned && (
        // The impression: a hairline cross pressed into the wax.
        <path
          d="M11 16h10M16 11v10"
          stroke="var(--color-paper)"
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.75"
        />
      )}
    </svg>
  )
}

/**
 * A hairline that fills. The product's progress bar, and deliberately not a bar:
 * the page is already made of rules, so progress is one of them drawn partway.
 */
export function RuleMeter({
  fraction,
  label,
  className = '',
}: {
  fraction: number
  label: string
  className?: string
}) {
  const percent = Math.round(Math.min(1, Math.max(0, fraction)) * 100)
  return (
    <div
      className={`h-px w-full bg-rule ${className}`}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className="h-px bg-accent transition-[width] duration-500 ease-paper"
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}

/**
 * The week, as seven marks.
 *
 * Filled for a day worked, hollow for one not. Days beyond the target are drawn
 * too, because the target is a floor a learner set and not a ceiling anyone
 * imposed.
 */
export function WeekDots({
  daysActive,
  target,
  className = '',
}: {
  daysActive: number
  target: number
  className?: string
}) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`} aria-hidden>
      {Array.from({ length: 7 }, (_, i) => {
        const worked = i < daysActive
        const withinTarget = i < target
        return (
          <span
            key={i}
            className={
              worked
                ? 'size-1.5 rounded-full bg-accent'
                : withinTarget
                  ? 'size-1.5 rounded-full border border-rule-strong'
                  : 'size-1.5 rounded-full border border-rule'
            }
          />
        )
      })}
    </span>
  )
}
