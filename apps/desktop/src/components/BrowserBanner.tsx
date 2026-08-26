import { useState } from 'react'
import { MonitorSmartphone } from 'lucide-react'

/**
 * Shown when the frontend is running in a plain browser tab (`pnpm dev:web`)
 * rather than inside the Tauri window. Everything except the terminal and Run
 * works there, so this explains the missing half instead of letting `invoke`
 * throw somewhere confusing.
 */
export function BrowserBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div role="status" className="flex min-w-0 shrink-0 flex-wrap items-center gap-x-2.5 gap-y-1 border-y border-warn/35 bg-warn-wash px-3 py-2 text-caption">
      <MonitorSmartphone aria-hidden className="size-4 shrink-0 text-warn" />
      <p className="min-w-0 text-ink-soft">
        <span className="font-medium text-ink">Browser preview.</span> The terminal and the Run
        button need the desktop shell — start it with{' '}
        <code className="font-mono">pnpm dev:desktop</code>. Reading, editing and progress all work
        here.
      </p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="ml-auto min-h-9 shrink-0 rounded-field px-2 py-1 text-caption font-medium text-ink-soft transition-colors duration-200 hover:bg-warn/10 hover:text-ink"
      >
        Dismiss
      </button>
    </div>
  )
}
