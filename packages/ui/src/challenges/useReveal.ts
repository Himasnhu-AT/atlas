'use client'

import { useEffect, useRef } from 'react'

/**
 * The arrival entrance, for something that appears because of a click.
 *
 * `Reveal` fires on an IntersectionObserver, which never fires for a node
 * mounted below the fold or already past it. An element injected in response
 * to a click therefore stays at `opacity: 0` while being perfectly present to
 * a screen reader. That has happened in this codebase before and DESIGN.md
 * records it. This sets `data-shown` on the next frame instead.
 */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    const frame = requestAnimationFrame(() => node.setAttribute('data-shown', ''))
    return () => cancelAnimationFrame(frame)
  }, [])

  return ref
}
