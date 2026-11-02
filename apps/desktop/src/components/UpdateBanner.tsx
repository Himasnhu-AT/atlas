import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { check, type Update } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

type State =
  | { kind: 'idle' }
  | { kind: 'available'; update: Update }
  | { kind: 'installing'; update: Update; percent: number | null }
  | { kind: 'failed'; update: Update; message: string }

/**
 * Offers a newer release when one is published.
 *
 * The check runs once per launch against the manifest in tauri.conf.json, and
 * nothing is downloaded until the learner asks: an install restarts the app,
 * which must never happen in the middle of someone's work. A failed check
 * (offline, GitHub down) shows nothing, because the app works offline and an
 * update is never urgent enough to interrupt that.
 */
export function UpdateBanner() {
  const [state, setState] = useState<State>({ kind: 'idle' })

  useEffect(() => {
    if (import.meta.env.DEV) return
    let cancelled = false
    check()
      .then((update) => {
        if (update && !cancelled) setState({ kind: 'available', update })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (state.kind === 'idle') return null

  const { update } = state

  async function install() {
    let total = 0
    let received = 0
    setState({ kind: 'installing', update, percent: null })
    try {
      await update.downloadAndInstall((event) => {
        if (event.event === 'Started') total = event.data.contentLength ?? 0
        if (event.event === 'Progress') {
          received += event.data.chunkLength
          if (total > 0) {
            setState({ kind: 'installing', update, percent: Math.round((received / total) * 100) })
          }
        }
      })
      // Windows hands over to the installer and exits before this line.
      await relaunch()
    } catch (err) {
      setState({ kind: 'failed', update, message: err instanceof Error ? err.message : String(err) })
    }
  }

  return (
    <div
      role="status"
      className="flex min-w-0 shrink-0 flex-wrap items-center gap-x-2.5 gap-y-1 border-y border-accent/30 bg-accent-wash px-3 py-2 text-caption"
    >
      <Download aria-hidden className="size-4 shrink-0 text-accent" />
      <p className="min-w-0 text-ink-soft">
        {state.kind === 'available' && (
          <>
            <span className="font-medium text-ink">Version {update.version} is available.</span>{' '}
            Installing restarts the app. Your work is saved as you type.
          </>
        )}
        {state.kind === 'installing' && (
          <>
            <span className="font-medium text-ink">Updating to {update.version}</span>
            {state.percent === null ? '…' : ` (${state.percent}%)`}
          </>
        )}
        {state.kind === 'failed' && (
          <>
            <span className="font-medium text-ink">The update did not install.</span>{' '}
            {state.message}
          </>
        )}
      </p>
      {state.kind !== 'installing' && (
        <div className="ml-auto flex shrink-0 gap-1">
          <button
            type="button"
            onClick={install}
            className="min-h-9 rounded-field bg-ink px-3 py-1 text-caption font-medium text-paper transition-colors duration-200 hover:bg-accent-deep"
          >
            {state.kind === 'failed' ? 'Try again' : 'Install and restart'}
          </button>
          <button
            type="button"
            onClick={() => setState({ kind: 'idle' })}
            className="min-h-9 rounded-field px-2 py-1 text-caption font-medium text-ink-soft transition-colors duration-200 hover:bg-accent/10 hover:text-ink"
          >
            Later
          </button>
        </div>
      )}
    </div>
  )
}
