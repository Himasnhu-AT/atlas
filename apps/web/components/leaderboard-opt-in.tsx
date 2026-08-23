'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

/** Joining and leaving are the same size of decision, so they are the same control. */
export function LeaderboardOptIn({ optedIn }: { optedIn: boolean }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const router = useRouter()

  async function toggle() {
    setBusy(true)
    setError(false)
    try {
      const response = await fetch('/api/game/settings', {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ leaderboardOptIn: !optedIn }),
      })
      if (!response.ok) throw new Error(String(response.status))
      router.refresh()
    } catch {
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
        className={
          optedIn
            ? 'inline-flex min-h-11 items-center rounded-field border border-rule-strong px-5 text-caption font-medium text-ink-soft transition-colors duration-200 ease-paper hover:text-ink disabled:opacity-60'
            : 'inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60'
        }
      >
        {optedIn ? 'Leave the board' : 'Join the board'}
      </button>

      {error && (
        <span role="alert" className="text-caption text-fail">
          Could not save that. Check your connection and try again.
        </span>
      )}
    </div>
  )
}
