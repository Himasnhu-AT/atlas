import { X } from 'lucide-react'
import { cn } from '@learn/ui'

export interface EditorFile {
  /** Stable identity — the workspace-relative path works well here. */
  id: string
  /** Label shown on the tab. */
  name: string
  /** Shows the unsaved dot. */
  dirty?: boolean
}

export interface FileTabsProps {
  files: EditorFile[]
  activeId: string | null
  onSelect: (id: string) => void
  /** Omit to render tabs that cannot be closed. */
  onClose?: (id: string) => void
  className?: string
}

/**
 * Tab strip for the editor pane.
 *
 * Roving `tabIndex` keeps the strip to a single tab stop; left/right arrows move
 * between files the way a real tab list does.
 */
export function FileTabs({ files, activeId, onSelect, onClose, className }: FileTabsProps) {
  if (files.length === 0) return null

  const move = (delta: number) => {
    const index = files.findIndex((file) => file.id === activeId)
    if (index < 0) return
    const next = files[(index + delta + files.length) % files.length]
    if (next) onSelect(next.id)
  }

  return (
    <div
      role="tablist"
      aria-label="Open files"
      className={cn(
        'flex min-h-9 items-stretch gap-px overflow-x-auto border-b border-rule bg-paper-sunken',
        className,
      )}
      onKeyDown={(event) => {
        if (event.key === 'ArrowRight') {
          event.preventDefault()
          move(1)
        } else if (event.key === 'ArrowLeft') {
          event.preventDefault()
          move(-1)
        }
      }}
    >
      {files.map((file) => {
        const active = file.id === activeId
        return (
          <div
            key={file.id}
            className={cn(
              'group flex shrink-0 items-center gap-1.5 border-r border-rule pr-1.5 text-xs',
              active ? 'bg-paper-raised text-ink' : 'text-ink-soft hover:bg-paper-sunken',
            )}
          >
            <button
              type="button"
              role="tab"
              aria-selected={active}
              tabIndex={active ? 0 : -1}
              title={file.id}
              onClick={() => onSelect(file.id)}
              className="flex items-center gap-1.5 py-2 pl-3 font-mono outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <span className="max-w-48 truncate">{file.name}</span>
              {file.dirty ? (
                <span
                  aria-label="Unsaved changes"
                  className="size-1.5 shrink-0 rounded-full bg-accent"
                />
              ) : null}
            </button>
            {onClose ? (
              <button
                type="button"
                tabIndex={-1}
                aria-label={`Close ${file.name}`}
                onClick={() => onClose(file.id)}
                className="rounded p-0.5 text-muted opacity-0 transition hover:bg-paper-sunken hover:text-ink focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-accent group-hover:opacity-100"
              >
                <X className="size-3" aria-hidden="true" />
              </button>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
