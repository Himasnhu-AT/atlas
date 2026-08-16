'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

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
  const router = useRouter()

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

      {error && (
        <span role="alert" className="text-caption text-fail">
          Could not save that. Check your connection and try again.
        </span>
      )}
    </div>
  )
}
