'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import type { QuestState } from '@atlas/core'

import { Rule } from './layout'

/**
 * Today's quests, and the week's.
 *
 * A claim is a button rather than an automatic payout because collecting is the
 * satisfying half, and because the server re-derives completion anyway: pressing
 * it asks a question the server can refuse.
 */
export function QuestList({ quests }: { quests: QuestState[] }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const router = useRouter()

  async function claim(claimKey: string) {
    setBusy(claimKey)
    setError(false)
    try {
      const response = await fetch('/api/game/quests/claim', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ claimKey }),
      })
      if (!response.ok) throw new Error(String(response.status))
      router.refresh()
    } catch {
      setError(true)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mt-4">
      <Rule />
      {quests.map((quest) => (
        <div key={quest.claimKey} className="border-b border-rule py-6">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
            <p className={quest.claimed ? 'text-muted' : 'text-ink'}>{quest.title}</p>

            <span className="font-mono text-caption tabular-nums text-muted">
              {quest.progress}/{quest.target}
            </span>

            {quest.period === 'weekly' && (
              <span className="text-eyebrow font-medium uppercase text-muted">this week</span>
            )}

            <span className="sm:ml-auto">
              {quest.claimed ? (
                <span className="text-caption text-pass">claimed · {quest.points} xp</span>
              ) : quest.complete ? (
                <button
                  type="button"
                  onClick={() => claim(quest.claimKey)}
                  disabled={busy === quest.claimKey}
                  className="inline-flex min-h-11 items-center rounded-field bg-ink px-4 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60"
                >
                  Claim {quest.points} xp
                </button>
              ) : (
                <span className="text-caption text-muted">{quest.points} xp</span>
              )}
            </span>
          </div>
        </div>
      ))}

      {error && (
        <p role="alert" className="mt-4 text-caption text-fail">
          Could not claim that. Check your connection and try again.
        </p>
      )}
    </div>
  )
}
