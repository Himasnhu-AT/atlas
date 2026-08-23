import {
  ChevronLeft,
  ChevronRight,
  CircleCheckBig,
  Eye,
  Play,
  RotateCcw,
} from 'lucide-react'
import { Button, cn } from '@atlas/ui'

export interface ToolbarProps {
  /** Disabled with `runDisabledReason` shown as the tooltip when false. */
  canRun: boolean
  runDisabledReason?: string
  running: boolean
  onRun: () => void

  canEdit: boolean
  onReset: () => void
  hasSolution: boolean
  onShowSolution: () => void

  done: boolean
  completing: boolean
  onMarkComplete: () => void

  onPrevious?: (() => void) | undefined
  onNext?: (() => void) | undefined
}

/** The action bar for the lesson on screen. Sits directly under the header. */
export function Toolbar({
  canRun,
  runDisabledReason,
  running,
  onRun,
  canEdit,
  onReset,
  hasSolution,
  onShowSolution,
  done,
  completing,
  onMarkComplete,
  onPrevious,
  onNext,
}: ToolbarProps) {
  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-rule bg-paper-raised px-3">
      <Button
        variant="primary"
        size="sm"
        onClick={onRun}
        loading={running}
        disabled={!canRun}
        title={canRun ? 'Write the buffer to the workspace and run it (⌘⏎)' : runDisabledReason}
        iconLeft={<Play aria-hidden />}
      >
        {running ? 'Running…' : 'Run'}
      </Button>

      <Button
        variant="secondary"
        size="sm"
        onClick={onReset}
        disabled={!canEdit}
        title="Discard your changes and restore the starter code"
        iconLeft={<RotateCcw aria-hidden />}
      >
        Reset
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={onShowSolution}
        disabled={!hasSolution}
        title={
          hasSolution
            ? 'Replace the buffer with the reference solution'
            : 'This exercise ships no reference solution'
        }
        iconLeft={<Eye aria-hidden />}
      >
        Solution
      </Button>

      <div aria-hidden className="mx-1 h-5 w-px bg-rule" />

      <Button
        variant={done ? 'ghost' : 'secondary'}
        size="sm"
        onClick={onMarkComplete}
        loading={completing}
        disabled={done || completing}
        title={done ? 'Already marked complete' : 'Mark this lesson complete'}
        iconLeft={<CircleCheckBig aria-hidden className={cn(done && 'text-pass')} />}
      >
        {done ? 'Completed' : 'Mark complete'}
      </Button>

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          iconOnly
          onClick={onPrevious}
          disabled={!onPrevious}
          title="Previous lesson"
          aria-label="Previous lesson"
        >
          <ChevronLeft aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          iconOnly
          onClick={onNext}
          disabled={!onNext}
          title="Next lesson"
          aria-label="Next lesson"
        >
          <ChevronRight aria-hidden />
        </Button>
      </div>
    </div>
  )
}
