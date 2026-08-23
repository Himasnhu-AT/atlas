'use client'

import { useState } from 'react'

export function PairForm({ initialCode }: { initialCode: string }) {
  const [code, setCode] = useState(initialCode)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ name: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)

    try {
      const response = await fetch('/api/devices/approve', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ userCode: code.trim().toUpperCase() }),
      })

      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: string }
        setError(body.detail ?? 'That code did not work.')
        return
      }

      setDone((await response.json()) as { name: string })
    } catch {
      setError('Could not reach the server. Check your connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="border-y-2 border-pass py-8">
        <p className="text-title text-ink">{done.name} is connected.</p>
        <p className="mt-3 max-w-[52ch] text-ink-soft">
          Go back to the app. It is already collecting your progress.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-sm">
      <label htmlFor="code" className="text-caption font-medium text-ink">
        The code the app is showing
      </label>
      <input
        id="code"
        name="code"
        value={code}
        onChange={(event) => setCode(event.target.value)}
        autoComplete="off"
        spellCheck={false}
        placeholder="XXXX-XXXX"
        className="mt-3 block min-h-11 w-full border-b border-rule-strong bg-transparent pb-2 font-mono text-lead tracking-[0.12em] text-ink uppercase outline-none focus-visible:border-accent"
      />

      <button
        type="submit"
        disabled={busy || code.trim().length < 4}
        className="mt-6 inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60"
      >
        {busy ? 'Connecting…' : 'Connect'}
      </button>

      {error && (
        <p role="alert" className="mt-4 text-caption text-fail">
          {error}
        </p>
      )}
    </form>
  )
}
