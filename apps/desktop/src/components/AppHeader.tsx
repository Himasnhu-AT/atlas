import { type ReactNode } from 'react'
import { LayoutTemplate, PanelBottomOpen, Terminal } from 'lucide-react'
import { cn } from '@atlas/ui'

export interface AppHeaderProps {
  moduleTitle: string
  lessonTitle: string
  terminalCollapsed: boolean
  onShowTerminal: () => void
  onResetLayout: () => void
}

/** Window chrome: where you are, plus the controls that are not lesson actions. */
export function AppHeader({
  moduleTitle,
  lessonTitle,
  terminalCollapsed,
  onShowTerminal,
  onResetLayout,
}: AppHeaderProps) {
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-rule bg-paper-raised px-3">
      <span className="inline-flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight text-ink">
        <Terminal aria-hidden className="size-4 text-accent" />
        Practice
      </span>

      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-xs">
        <span aria-hidden className="text-muted">
          /
        </span>
        <span className="truncate text-ink-soft">{moduleTitle}</span>
        <span aria-hidden className="text-muted">
          /
        </span>
        <span className="truncate font-medium text-ink">{lessonTitle}</span>
      </nav>

      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        {terminalCollapsed ? (
          <IconAction label="Show the terminal" onClick={onShowTerminal}>
            <PanelBottomOpen aria-hidden className="size-4" />
          </IconAction>
        ) : null}
        <IconAction label="Reset the pane layout" onClick={onResetLayout}>
          <LayoutTemplate aria-hidden className="size-4" />
        </IconAction>
        
      </div>
    </header>
  )
}

function IconAction({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={cn(
        'inline-flex size-9 items-center justify-center rounded-field border border-rule',
        'bg-paper-raised text-ink-soft shadow-none transition-colors duration-150 ease-paper',
        'hover:border-rule-strong hover:bg-paper-sunken hover:text-ink',
      )}
    >
      {children}
    </button>
  )
}

