'use client'

import { useEffect, useMemo, useRef, type ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'
import { copyCodeFrom, renderMarkdown } from '../lib/markdown'

export interface MarkdownProps
  extends Omit<ComponentPropsWithRef<'div'>, 'children' | 'dangerouslySetInnerHTML' | 'ref'> {
  /** Markdown source. Compiled with `marked`, then sanitised with DOMPurify. */
  children: string
  /** Tighter type scale for previews and sidebars. */
  compact?: boolean
}

const COPIED_RESET_MS = 1600

/**
 * Renders lesson markdown.
 *
 * The HTML handed to `dangerouslySetInnerHTML` has already been through
 * DOMPurify (see `lib/markdown.ts`) — that is the only reason this is safe, and
 * the sanitising step must never be bypassed.
 */
export function Markdown({ children, compact = false, className, ...props }: MarkdownProps) {
  const html = useMemo(() => renderMarkdown(children), [children])
  const containerRef = useRef<HTMLDivElement | null>(null)

  // Copy buttons are plain DOM inside the sanitised markup, so behaviour is
  // attached by delegation rather than by rendering React nodes into it.
  useEffect(() => {
    const root = containerRef.current
    if (!root) return

    const timers = new Set<ReturnType<typeof setTimeout>>()

    const handleClick = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const trigger = target.closest<HTMLElement>('[data-copy-code]')
      if (!trigger || !root.contains(trigger)) return

      void copyCodeFrom(trigger).then((ok) => {
        trigger.dataset['copied'] = String(ok)
        trigger.textContent = ok ? 'Copied' : 'Press ⌘C'
        const timer = setTimeout(() => {
          delete trigger.dataset['copied']
          trigger.textContent = 'Copy'
          timers.delete(timer)
        }, COPIED_RESET_MS)
        timers.add(timer)
      })
    }

    root.addEventListener('click', handleClick)
    return () => {
      root.removeEventListener('click', handleClick)
      for (const timer of timers) clearTimeout(timer)
    }
  }, [html])

  return (
    <div
      ref={containerRef}
      className={cn('prose-learn', compact && 'prose-compact', className)}
      dangerouslySetInnerHTML={{ __html: html }}
      {...props}
    />
  )
}
