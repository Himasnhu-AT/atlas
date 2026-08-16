import { PanelBottomClose, TerminalSquare } from 'lucide-react'
import { cn } from '@learn/ui'
import { TerminalPane } from './terminal'

export interface TerminalSlotProps {
  /** False in a plain browser tab: there is no pty to attach to. */
  available: boolean
  /**
   * The terminal owns its pty session (it is the thing that knows its own
   * cols/rows), and publishes the id so Run can type into that same shell.
   */
  onSessionChange: (sessionId: string | null) => void
  /** Surfaced in the status bar — a dead shell must not fail silently. */
  onError: (message: string) => void
  onCollapse: () => void
}

/** Right-hand pane: a real login shell rooted in the practice workspace. */
export function TerminalSlot({
  available,
  onSessionChange,
  onError,
  onCollapse,
}: TerminalSlotProps) {
  return (
    <div className="flex h-full min-h-0 w-full flex-col border-l border-rule bg-paper-raised">
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-rule px-3">
        <TerminalSquare aria-hidden className="size-3.5 shrink-0 text-muted" />
        <span className="text-xs font-medium text-ink-soft">Terminal</span>
        <button
          type="button"
          onClick={onCollapse}
          title="Hide the terminal"
          aria-label="Hide the terminal"
          className={cn(
            'ml-auto inline-flex size-6 items-center justify-center rounded-field',
            'text-muted transition-colors duration-150 hover:bg-paper-sunken hover:text-ink',
          )}
        >
          <PanelBottomClose aria-hidden className="size-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {available ? (
          <TerminalPane
            onSessionChange={onSessionChange}
            onError={onError}
            className="h-full"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <TerminalSquare aria-hidden className="size-6 text-muted" />
            <p className="text-sm font-medium text-ink">No shell in the browser</p>
            <p className="max-w-xs text-xs leading-relaxed text-ink-soft">
              The embedded terminal is a real pseudo terminal supplied by the Tauri backend. Launch
              the desktop app with <code className="font-mono">pnpm dev:desktop</code> to use it.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
