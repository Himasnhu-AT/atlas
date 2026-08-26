import { type ReactNode } from 'react'
import { LayoutTemplate, PanelBottomOpen, Terminal } from 'lucide-react'

import { cn } from '@atlas/ui'

import { SyncPanel } from './SyncPanel'

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
    <header className="flex h-12 min-w-0 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-rule bg-paper-raised px-3">
      <span className="inline-flex shrink-0 items-center gap-2 text-caption font-medium tracking-[0.08em] text-muted uppercase">
        <Terminal aria-hidden className="size-4 text-accent" />
        Practice
      </span>

      <nav aria-label="Breadcrumb" className="flex min-w-0 flex-1 items-baseline gap-2 text-caption">
        <span aria-hidden className="text-rule-strong">
          /
        </span>
        <span className="truncate text-ink-soft">{moduleTitle}</span>
        <span aria-hidden className="text-rule-strong">
          /
        </span>
        <span className="truncate font-serif text-[15px] leading-none tracking-[-0.005em] text-ink">
          {lessonTitle}
        </span>
      </nav>

      <div className="ml-auto flex shrink-0 items-center gap-1.5">
        <SyncPanel />
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
        'bg-paper-raised text-ink-soft shadow-none transition-colors duration-200 ease-paper',
        'hover:border-rule-strong hover:bg-paper-sunken hover:text-ink',
      )}
    >
      {children}
    </button>
  )
}
