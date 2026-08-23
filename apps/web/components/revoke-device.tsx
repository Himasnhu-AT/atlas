'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'

/**
 * Disconnecting a device asks first.
 *
 * It is not destructive to the learner's progress, which stays on the server,
 * but it does stop a machine syncing without warning, and the confirm is what
 * stops a mis-click doing that silently.
 */
export function RevokeDevice({ deviceId, name }: { deviceId: string; name: string }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const router = useRouter()

  async function revoke() {
    setBusy(true)
    setError(false)
    try {
      const response = await fetch('/api/devices/revoke', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ deviceId }),
      })
      if (!response.ok) throw new Error(String(response.status))
      router.refresh()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  if (!confirming) {
    return (
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="inline-flex min-h-11 items-center rounded-field border border-rule px-4 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:border-rule-strong hover:text-ink"
      >
        Disconnect
      </button>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-caption text-ink-soft">Disconnect {name}?</span>
      <button
        type="button"
        onClick={revoke}
        disabled={busy}
        className="inline-flex min-h-11 items-center rounded-field bg-fail px-4 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-fail-deep disabled:opacity-60"
      >
        Disconnect
      </button>
      <button
        type="button"
        onClick={() => setConfirming(false)}
        className="inline-flex min-h-11 items-center px-2 text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink"
      >
        Keep
      </button>
      {error && (
        <span role="alert" className="text-caption text-fail">
          Could not disconnect that.
        </span>
      )}
    </div>
  )
}
