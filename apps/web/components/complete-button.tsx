'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'

export function CompleteButton({
  lessonId,
  moduleId,
  initiallyComplete,
}: {
  lessonId: string
  moduleId: string
  initiallyComplete: boolean
}) {
  const [complete, setComplete] = useState(initiallyComplete)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  /** XP just earned, stamped in the margin and then let go. */
  const [stamp, setStamp] = useState<number | null>(null)
  const stampRef = useRef<HTMLSpanElement | null>(null)
  const router = useRouter()

  /**
   * Arrive using the page's own gesture.
   *
   * `[data-reveal]` is opacity 0 until something adds `data-shown`, which for
   * scrolled content is the IntersectionObserver in `Reveal`. Nothing observes a
   * span injected after a click, so setting the attribute alone left the stamp
   * invisible: it was rendered, announced to a screen reader, and never drawn.
   * Flipping it on the next frame is what the observer would have done.
   */
  useEffect(() => {
    if (stamp === null) return
    const frame = requestAnimationFrame(() => {
      stampRef.current?.setAttribute('data-shown', '')
    })
    return () => cancelAnimationFrame(frame)
  }, [stamp])

  // The stamp is a moment, not a state. It clears itself so the page does not
  // keep congratulating someone who has moved on to the next lesson.
  useEffect(() => {
    if (stamp === null) return
    const timer = setTimeout(() => setStamp(null), 4000)
    return () => clearTimeout(timer)
  }, [stamp])

  async function toggle() {
    setBusy(true)
    setError(false)

    const next = !complete
    // Optimistic: the round trip is slower than the reader's attention, and the
    // failure path below puts it back.
    setComplete(next)

    try {
      const response = await fetch('/api/progress', {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          lessonId,
          moduleId,
          status: next ? 'completed' : 'in_progress',
        }),
      })
      if (!response.ok) throw new Error(String(response.status))

      const body = (await response.json()) as { awarded?: number }
      if (next && typeof body.awarded === 'number' && body.awarded > 0) {
        setStamp(body.awarded)
      }
      router.refresh()
    } catch {
      setComplete(!next)
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={complete}
        className={
          complete
            ? 'inline-flex min-h-11 items-center gap-2.5 rounded-field border border-pass px-5 text-caption font-medium text-pass transition-colors duration-200 ease-paper disabled:opacity-60'
            : 'inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60'
        }
      >
        {complete && <span aria-hidden>&#10003;</span>}
        {complete ? 'Completed' : 'Mark complete'}
      </button>

      {stamp !== null && (
        <span
          ref={stampRef}
          // Announced, because a number appearing beside a button is the whole
          // feedback and a screen reader would otherwise get silence.
          role="status"
          data-reveal
          className="font-mono text-caption tabular-nums text-accent-deep"
        >
          +{stamp} xp
        </span>
      )}

      {error && (
        <span role="alert" className="text-caption text-fail">
          Could not save that. Check your connection and try again.
        </span>
      )}
    </div>
  )
}
