import type { ReactNode } from 'react'

import { Reveal } from './reveal'

/**
 * The page vocabulary.
 *
 * Every page is built from these. If a page needs a shape that is not here, add
 * it here and use it, rather than inventing a one-off arrangement inline: the
 * point of a small vocabulary is that a page nobody has written yet already
 * looks like it belongs.
 *
 * There are no cards. A card is the lazy container, and a grid of same-size
 * cards is the fastest way to make a considered product look generated. Where a
 * card is tempting, the answer here is a ruled row.
 */

/** The column. Nothing sits outside it. */
export function Wrap({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`mx-auto w-full max-w-page px-6 sm:px-8 ${className}`}>{children}</div>
}

/** The small caps label that opens a page or a late section. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="text-eyebrow font-medium uppercase text-muted">{children}</p>
  )
}

/**
 * The opening of an inner page: label, h1, and one serif paragraph.
 *
 * `title` takes JSX so a single word can carry the accent, which is the only
 * emphasis the palette has.
 */
export function PageHeader({
  eyebrow,
  title,
  lead,
}: {
  eyebrow?: string
  title: ReactNode
  lead?: ReactNode
}) {
  return (
    <header className="max-w-[34ch] sm:max-w-[46ch]">
      {eyebrow && (
        <Reveal>
          <Eyebrow>{eyebrow}</Eyebrow>
        </Reveal>
      )}
      <Reveal delay={0.06}>
        <h1 className="mt-4 text-title text-ink">{title}</h1>
      </Reveal>
      {lead && (
        <Reveal delay={0.13}>
          <p className="mt-5 max-w-[56ch] font-serif text-lead text-ink-soft">{lead}</p>
        </Reveal>
      )}
    </header>
  )
}

/**
 * The one list style: a narrow left column for a numeral or a status, and the
 * substance on the right. Collapses to a single column on small screens, where
 * a 4rem gutter would eat the text.
 */
export function RuledList({ children }: { children: ReactNode }) {
  return (
    <div className="mt-12">
      <Rule />
      {children}
    </div>
  )
}

export function RuledRow({
  aside,
  title,
  meta,
  children,
  href,
  index = 0,
}: {
  aside?: ReactNode
  title: ReactNode
  meta?: ReactNode
  children?: ReactNode
  href?: string
  index?: number
}) {
  const body = (
    <div className="grid gap-x-8 gap-y-2 py-8 sm:grid-cols-[4.5rem_1fr] sm:py-9">
      {aside !== undefined && (
        <div className="font-mono text-caption tabular-nums text-muted">{aside}</div>
      )}
      <div className={aside === undefined ? 'sm:col-span-2' : undefined}>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h2 className="text-section text-ink">{title}</h2>
          {meta && <span className="text-caption text-muted sm:ml-auto">{meta}</span>}
        </div>
        {children && (
          <div className="mt-2 max-w-[62ch] text-ink-soft">{children}</div>
        )}
      </div>
    </div>
  )

  return (
    <Reveal delay={Math.min(index, 3) * 0.05}>
      <div className="group border-b border-rule">
        {href ? (
          <a
            href={href}
            className="block transition-colors duration-200 ease-paper hover:bg-paper-raised"
          >
            {body}
          </a>
        ) : (
          body
        )}
      </div>
    </Reveal>
  )
}

/**
 * A standalone hairline.
 *
 * It is drawn from the left rather than faded in, because the gesture this
 * product uses for arrival is ruling a line on paper.
 */
export function Rule({ className = '' }: { className?: string }) {
  return (
    <div
      data-rule
      className={`h-px w-full origin-left bg-rule ${className}`}
      aria-hidden
    />
  )
}

/** Closes a page. At most one, and only when the line earns it. */
export function PullQuote({ children }: { children: ReactNode }) {
  return (
    <Reveal>
      <p className="mt-20 max-w-[56ch] font-serif text-quote italic text-ink">{children}</p>
    </Reveal>
  )
}
