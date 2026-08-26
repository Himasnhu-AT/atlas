'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export function AdminDeviceRevokeButton({
  userId,
  deviceId,
  isRevoked,
}: {
  userId: string
  deviceId: string
  isRevoked: boolean
}) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  async function revoke() {
    if (!confirm('Revoke this paired device? The user will need to pair it again.')) return
    setLoading(true)
    try {
      const res = await fetch('/api/admin/devices/revoke', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ userId, deviceId }),
      })
      if (res.ok) {
        router.refresh()
      }
    } finally {
      setLoading(false)
    }
  }

  if (isRevoked) {
    return <span className="text-[12px] text-muted">Revoked</span>
  }

  return (
    <button
      type="button"
      onClick={revoke}
      disabled={loading}
      className="inline-flex min-h-8 items-center rounded-field border border-rule px-3 text-[12px] text-muted hover:border-rule-strong hover:text-ink disabled:opacity-50"
    >
      {loading ? 'Revoking…' : 'Revoke'}
    </button>
  )
}
