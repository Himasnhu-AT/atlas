import { FileCode2 } from 'lucide-react'
import type { ExerciseLanguage as Language } from '@learn/learning'
import { Badge } from '@learn/ui'
import { CodeEditor } from './editor'

export interface EditorSlotProps {
  language: Language
  value: string
  onChange: (value: string) => void
  /** Workspace-relative path the buffer is written to on Run. */
  relPath: string | undefined
  /** True once the buffer differs from the exercise's starter code. */
  modified: boolean
  /** Bound to Cmd/Ctrl-Enter inside the editor. */
  onRun: () => void
}

/**
 * Centre-bottom pane: the buffer the learner edits.
 *
 * `<CodeEditor>` is owned by the editor agent — this wrapper only supplies the
 * chrome (path, language, run hint) and the controlled value.
 */
export function EditorSlot({
  language,
  value,
  onChange,
  relPath,
  modified,
  onRun,
}: EditorSlotProps) {
  return (
    <div className="flex h-full min-h-0 w-full flex-col border-t border-rule bg-paper-raised">
      <div className="flex h-9 shrink-0 items-center gap-2 border-b border-rule px-3">
        <FileCode2 aria-hidden className="size-3.5 shrink-0 text-muted" />
        <span className="truncate font-mono text-xs text-ink-soft">
          {relPath ?? 'scratch buffer (not saved to the workspace)'}
        </span>
        {modified ? (
          <Badge variant="warning" size="sm">
            modified
          </Badge>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <Badge variant="neutral" size="sm">
            {language}
          </Badge>
          <kbd className="rounded border border-rule bg-paper-sunken px-1.5 py-0.5 font-mono text-[0.6875rem] text-muted">
            ⌘⏎ run
          </kbd>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <CodeEditor
          value={value}
          onChange={onChange}
          onRun={onRun}
          language={language}
          className="h-full"
          ariaLabel={relPath ? `Editor for ${relPath}` : 'Scratch editor'}
        />
      </div>
    </div>
  )
}
