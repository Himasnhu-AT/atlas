'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export function ModerationControls({
  userId,
  initialExcluded,
}: {
  userId: string
  initialExcluded: boolean
}) {
  const router = useRouter()
  const [excluded, setExcluded] = useState(initialExcluded)
  const [loading, setLoading] = useState(false)
  const [points, setPoints] = useState('50')
  const [reason, setReason] = useState('Admin bonus')
  const [awardLoading, setAwardLoading] = useState(false)
  const [awardMessage, setAwardMessage] = useState<string | null>(null)

  async function toggleExcluded() {
    setLoading(true)
    try {
      const res = await fetch(`/api/admin/users/${userId}/exclude`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ excluded: !excluded }),
      })
      if (res.ok) {
        setExcluded(!excluded)
        router.refresh()
      }
    } finally {
      setLoading(false)
    }
  }

  async function awardXp(e: React.FormEvent) {
    e.preventDefault()
    setAwardLoading(true)
    setAwardMessage(null)
    try {
      const res = await fetch(`/api/admin/users/${userId}/award`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ points: parseInt(points, 10), reason }),
      })
      const data = await res.json()
      if (res.ok) {
        setAwardMessage(`Granted ${data.pointsAwarded} XP successfully.`)
        router.refresh()
      } else {
        setAwardMessage(`Error: ${data.error || 'Failed to award XP'}`)
      }
    } finally {
      setAwardLoading(false)
    }
  }

  return (
    <div className="space-y-6 rounded-sheet border border-rule bg-paper-raised p-6">
      <h3 className="font-serif text-title text-ink">Admin Controls</h3>

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-5">
        <div>
          <p className="text-caption font-medium text-ink">Leaderboard Standing</p>
          <p className="text-[12px] text-muted">
            {excluded
              ? 'This user is hidden from the public weekly league.'
              : 'This user is currently eligible to appear on the leaderboard.'}
          </p>
        </div>
        <button
          type="button"
          onClick={toggleExcluded}
          disabled={loading}
          className={`min-h-10 rounded-field px-4 text-caption font-medium transition-colors ${
            excluded
              ? 'bg-ink text-paper hover:bg-accent-deep'
              : 'border border-rule-strong bg-paper text-ink hover:bg-paper-sunken'
          } disabled:opacity-50`}
        >
          {loading
            ? 'Updating…'
            : excluded
              ? 'Restore to Leaderboard'
              : 'Exclude from Leaderboard'}
        </button>
      </div>

      <form onSubmit={awardXp} className="space-y-3">
        <p className="text-caption font-medium text-ink">Grant Manual XP</p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="number"
            value={points}
            onChange={(e) => setPoints(e.target.value)}
            min="1"
            max="10000"
            required
            className="w-24 rounded-field border border-rule bg-paper px-3 py-2 text-caption text-ink focus:border-ink focus:outline-none"
            placeholder="XP"
          />
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            className="min-w-[12rem] flex-1 rounded-field border border-rule bg-paper px-3 py-2 text-caption text-ink focus:border-ink focus:outline-none"
            placeholder="Reason (e.g. Exercise bug bounty)"
          />
          <button
            type="submit"
            disabled={awardLoading}
            className="min-h-10 rounded-field bg-ink px-4 text-caption font-medium text-paper transition-colors hover:bg-accent-deep disabled:opacity-50"
          >
            {awardLoading ? 'Awarding…' : 'Grant XP'}
          </button>
        </div>
        {awardMessage && (
          <p className="text-[12px] text-accent font-medium">{awardMessage}</p>
        )}
      </form>
    </div>
  )
}
