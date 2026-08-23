'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

/**
 * The learner sets their own target.
 *
 * This is the whole reason the product has a weekly target rather than a daily
 * streak: a goal you chose is information when you miss it, and a goal imposed
 * on you is a punishment. So the control is plain, the number is yours, and
 * lowering it is offered as readily as raising it.
 */
export function WeeklyTargetPicker({ target, chosen }: { target: number; chosen: boolean }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const router = useRouter()

  async function set(days: number) {
    setBusy(true)
    setError(false)
    try {
      const response = await fetch('/api/game/settings', {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ weeklyTarget: days }),
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
    <div>
      <p className="text-caption text-muted">
        {chosen
          ? 'Days a week you asked of yourself. Change it whenever it stops fitting.'
          : 'Pick a number of days a week. Nothing is lost by missing one, and you can change it whenever.'}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {[1, 2, 3, 4, 5, 6, 7].map((days) => (
          <button
            key={days}
            type="button"
            onClick={() => set(days)}
            disabled={busy}
            aria-pressed={chosen && days === target}
            className={
              chosen && days === target
                ? 'inline-flex size-11 items-center justify-center rounded-field border border-accent font-mono text-caption tabular-nums text-accent-deep disabled:opacity-60'
                : 'inline-flex size-11 items-center justify-center rounded-field border border-rule font-mono text-caption tabular-nums text-muted transition-colors duration-200 ease-paper hover:border-rule-strong hover:text-ink disabled:opacity-60'
            }
          >
            {days}
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-caption text-fail">
          Could not save that. Check your connection and try again.
        </p>
      )}
    </div>
  )
}
