'use client'

import { useEffect, useRef, type ReactNode } from 'react'

/**
 * Reveals its children when they are actually scrolled to, once.
 *
 * An entrance that has already finished by the time the reader arrives is worse
 * than no entrance, because the page then simply looks static to them. So this
 * fires on intersection rather than on mount.
 *
 * The hidden pre-state lives in CSS behind `@media (scripting: enabled)`, which
 * means a page whose JavaScript failed renders fully visible. Nothing here can
 * hide content permanently.
 */
export function Reveal({
  children,
  delay = 0,
  variant,
  className = '',
}: {
  children: ReactNode
  delay?: number
  /** `settle` is the focal entrance. One per page, at most. */
  variant?: 'settle'
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    // Respect the preference directly rather than relying on the CSS override
    // alone, so the observer never runs for someone who asked for stillness.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      node.setAttribute('data-shown', '')
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          entry.target.setAttribute('data-shown', '')
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.08, rootMargin: '0px 0px -6% 0px' },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      data-reveal={variant}
      style={delay ? { transitionDelay: `${delay}s` } : undefined}
      className={className}
    >
      {children}
    </div>
  )
}
