import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, File, Folder } from 'lucide-react'

import { projectList, type FileEntry } from '../../lib/ipc'
import { errorMessage } from '../../lib/errors'

/**
 * The project file tree.
 *
 * Children are fetched when a directory is first expanded rather than walked up
 * front. A repository is arbitrarily large and mostly irrelevant, and reading
 * all of it to render a few visible rows is how a file tree makes an editor
 * feel slow.
 */
export function FileTree({
  activePath,
  onOpenFile,
}: {
  activePath: string | null
  onOpenFile: (path: string) => void
}) {
  return (
    <nav aria-label="Project files" className="min-h-0 flex-1 overflow-y-auto py-2">
      <Directory rel="" depth={0} activePath={activePath} onOpenFile={onOpenFile} defaultOpen />
    </nav>
  )
}

function Directory({
  rel,
  depth,
  activePath,
  onOpenFile,
  defaultOpen = false,
}: {
  rel: string
  depth: number
  activePath: string | null
  onOpenFile: (path: string) => void
  defaultOpen?: boolean
}) {
  const open = defaultOpen
  const [entries, setEntries] = useState<FileEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setEntries(await projectList(rel))
      setError(null)
    } catch (cause) {
      setError(errorMessage(cause))
    }
  }, [rel])

  useEffect(() => {
    if (open && entries === null) void load()
  }, [open, entries, load])

  if (!open && depth > 0) return null

  return (
    <ul className={depth === 0 ? undefined : 'ml-3 border-l border-rule'}>
      {error && (
        <li className="px-3 py-1.5 text-caption text-fail" role="alert">
          {error}
        </li>
      )}

      {entries?.length === 0 && (
        <li className="px-3 py-1.5 text-caption text-muted">Empty</li>
      )}

      {entries?.map((entry) =>
        entry.isDir ? (
          <DirectoryRow
            key={entry.path}
            entry={entry}
            depth={depth}
            activePath={activePath}
            onOpenFile={onOpenFile}
          />
        ) : (
          <li key={entry.path}>
            <button
              type="button"
              onClick={() => onOpenFile(entry.path)}
              aria-current={entry.path === activePath ? 'true' : undefined}
              className={`flex min-h-9 w-full items-center gap-2 rounded-field px-3 py-1 text-left text-caption transition-colors duration-200 ease-paper ${
                entry.path === activePath
                  ? 'bg-paper-sunken text-ink'
                  : 'text-ink-soft hover:bg-paper-sunken hover:text-ink'
              }`}
              style={{ paddingLeft: `${12 + depth * 10}px` }}
            >
              <File aria-hidden className="size-3.5 shrink-0 text-muted" />
              <span className="truncate">{entry.name}</span>
            </button>
          </li>
        ),
      )}
    </ul>
  )
}

function DirectoryRow({
  entry,
  depth,
  activePath,
  onOpenFile,
}: {
  entry: FileEntry
  depth: number
  activePath: string | null
  onOpenFile: (path: string) => void
}) {
  const [open, setOpen] = useState(false)
  const Chevron = open ? ChevronDown : ChevronRight

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex min-h-9 w-full items-center gap-2 rounded-field px-3 py-1 text-left text-caption text-ink-soft transition-colors duration-200 ease-paper hover:bg-paper-sunken hover:text-ink"
        style={{ paddingLeft: `${12 + depth * 10}px` }}
      >
        <Chevron aria-hidden className="size-3.5 shrink-0 text-muted" />
        <Folder aria-hidden className="size-3.5 shrink-0 text-muted" />
        <span className="truncate">{entry.name}</span>
      </button>

      {open && (
        <Directory
          rel={entry.path}
          depth={depth + 1}
          activePath={activePath}
          onOpenFile={onOpenFile}
          defaultOpen
        />
      )}
    </li>
  )
}
