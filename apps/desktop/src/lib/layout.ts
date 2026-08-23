import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Pane geometry for the practice IDE, persisted to localStorage.
 *
 * Every fraction is the share of its container taken by the *first* pane of the
 * split it belongs to:
 *
 *   navFraction        navigator │ everything else
 *   workbenchFraction  lesson+editor column │ terminal
 *   lessonFraction     lesson body ─ over ─ editor
 */
export interface LayoutState {
  navFraction: number
  workbenchFraction: number
  lessonFraction: number
  navCollapsed: boolean
  terminalCollapsed: boolean
}

export type LayoutFraction = 'navFraction' | 'workbenchFraction' | 'lessonFraction'

export const DEFAULT_LAYOUT: LayoutState = {
  navFraction: 0.2,
  workbenchFraction: 0.62,
  lessonFraction: 0.48,
  navCollapsed: false,
  terminalCollapsed: false,
}

const STORAGE_KEY = 'atlas.desktop.layout'
const MIN_FRACTION = 0.12
const MAX_FRACTION = 0.88
/** Pointer drags fire far faster than localStorage should be written. */
const PERSIST_DELAY_MS = 180

export function clampFraction(value: number): number {
  if (!Number.isFinite(value)) return 0.5
  return Math.min(Math.max(value, MIN_FRACTION), MAX_FRACTION)
}

function readStored(): LayoutState {
  if (typeof localStorage === 'undefined') return DEFAULT_LAYOUT
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_LAYOUT
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return DEFAULT_LAYOUT
    const record = parsed as Record<string, unknown>

    return {
      navFraction: fraction(record['navFraction'], DEFAULT_LAYOUT.navFraction),
      workbenchFraction: fraction(record['workbenchFraction'], DEFAULT_LAYOUT.workbenchFraction),
      lessonFraction: fraction(record['lessonFraction'], DEFAULT_LAYOUT.lessonFraction),
      navCollapsed: boolean(record['navCollapsed'], DEFAULT_LAYOUT.navCollapsed),
      terminalCollapsed: boolean(record['terminalCollapsed'], DEFAULT_LAYOUT.terminalCollapsed),
    }
  } catch {
    // Corrupt or unreadable storage is not worth crashing the window over.
    return DEFAULT_LAYOUT
  }
}

function fraction(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? clampFraction(value) : fallback
}

function boolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function sameLayout(a: LayoutState, b: LayoutState): boolean {
  return (
    a.navFraction === b.navFraction &&
    a.workbenchFraction === b.workbenchFraction &&
    a.lessonFraction === b.lessonFraction &&
    a.navCollapsed === b.navCollapsed &&
    a.terminalCollapsed === b.terminalCollapsed
  )
}

export interface UseLayoutResult {
  layout: LayoutState
  setFraction: (key: LayoutFraction, value: number) => void
  toggleNav: () => void
  toggleTerminal: () => void
  reset: () => void
}

export function useLayout(): UseLayoutResult {
  const [layout, setLayout] = useState<LayoutState>(readStored)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<LayoutState | null>(null)

  const flush = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const next = pendingRef.current
    pendingRef.current = null
    if (next === null || typeof localStorage === 'undefined') return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    } catch (error) {
      console.warn('[desktop] could not persist the pane layout', error)
    }
  }, [])

  const persist = useCallback(
    (next: LayoutState) => {
      pendingRef.current = next
      if (timerRef.current !== null) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(flush, PERSIST_DELAY_MS)
    },
    [flush],
  )

  // Never lose the last drag: write through before the window goes away.
  useEffect(() => {
    const onHide = (): void => flush()
    window.addEventListener('pagehide', onHide)
    window.addEventListener('beforeunload', onHide)
    return () => {
      window.removeEventListener('pagehide', onHide)
      window.removeEventListener('beforeunload', onHide)
      flush()
    }
  }, [flush])

  const update = useCallback(
    (change: (current: LayoutState) => LayoutState) => {
      setLayout((current) => {
        const next = change(current)
        // Returning the identical object makes React bail out of the render.
        // This matters: a drag fires pointermove far faster than the clamped
        // fraction actually changes, and a held arrow key on a handle that is
        // already at its limit would otherwise re-render (and re-arm the
        // persist timer, so nothing is ever written) for as long as it repeats.
        if (sameLayout(current, next)) return current
        persist(next)
        return next
      })
    },
    [persist],
  )

  const setFraction = useCallback(
    (key: LayoutFraction, value: number) => {
      update((current) => ({ ...current, [key]: clampFraction(value) }))
    },
    [update],
  )

  const toggleNav = useCallback(() => {
    update((current) => ({ ...current, navCollapsed: !current.navCollapsed }))
  }, [update])

  const toggleTerminal = useCallback(() => {
    update((current) => ({ ...current, terminalCollapsed: !current.terminalCollapsed }))
  }, [update])

  const reset = useCallback(() => {
    update(() => DEFAULT_LAYOUT)
  }, [update])

  return { layout, setFraction, toggleNav, toggleTerminal, reset }
}
