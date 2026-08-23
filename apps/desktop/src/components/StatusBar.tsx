import { CircleAlert, CircleCheck, Cloud, FolderOpen, HardDrive, Loader2 } from 'lucide-react'
import { cn } from '@atlas/ui'

export type StatusTone = 'info' | 'success' | 'error' | 'busy'

export interface StatusMessage {
  tone: StatusTone
  text: string
}

export interface StatusBarProps {
  message: StatusMessage | null
  workspacePath: string | null
  /** True once the terminal has published a live pty session. */
  sessionReady: boolean
  desktop: boolean
  offline: boolean
}

const TONES: Record<StatusTone, string> = {
  info: 'text-ink-soft',
  success: 'text-pass',
  error: 'text-fail',
  busy: 'text-ink-soft',
}

/** Bottom strip: what just happened, and what this app is connected to. */
export function StatusBar({
  message,
  workspacePath,
  sessionReady,
  desktop,
  offline,
}: StatusBarProps) {
  return (
    <footer className="flex h-7 shrink-0 items-center gap-3 border-t border-rule bg-paper-raised px-3 text-[0.6875rem]">
      <span
        aria-live="polite"
        className={cn('inline-flex min-w-0 items-center gap-1.5', TONES[message?.tone ?? 'info'])}
      >
        {message?.tone === 'success' ? <CircleCheck aria-hidden className="size-3" /> : null}
        {message?.tone === 'error' ? <CircleAlert aria-hidden className="size-3" /> : null}
        {message?.tone === 'busy' ? (
          <Loader2 aria-hidden className="size-3 animate-spin" />
        ) : null}
        <span className="truncate">{message?.text ?? 'Ready'}</span>
      </span>

      <span className="ml-auto flex shrink-0 items-center gap-3 text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn(
              'size-1.5 rounded-full',
              desktop && sessionReady ? 'bg-pass' : 'bg-muted',
            )}
          />
          {desktop ? (sessionReady ? 'shell ready' : 'shell starting…') : 'browser preview'}
        </span>

        {workspacePath ? (
          <span className="inline-flex max-w-[24rem] items-center gap-1.5" title={workspacePath}>
            <FolderOpen aria-hidden className="size-3" />
            <span className="truncate font-mono">{workspacePath}</span>
          </span>
        ) : null}

        <span className="inline-flex items-center gap-1.5">
          {offline ? <HardDrive aria-hidden className="size-3" /> : <Cloud aria-hidden className="size-3" />}
          {offline ? 'local only' : 'synced'}
        </span>
      </span>
    </footer>
  )
}
