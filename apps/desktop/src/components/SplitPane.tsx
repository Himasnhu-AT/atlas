import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { cn } from '@learn/ui'
import { clampFraction } from '../lib/layout'

export interface SplitPaneProps {
  /** `horizontal` puts the panes side by side; `vertical` stacks them. */
  direction: 'horizontal' | 'vertical'
  first: ReactNode
  second: ReactNode
  /** Share of the container taken by `first`, 0-1. */
  fraction: number
  onFractionChange: (fraction: number) => void
  /** Double-clicking the handle snaps back to this. */
  defaultFraction?: number
  /** Accessible name for the divider, e.g. "Resize the lesson pane". */
  label: string
  className?: string
}

const KEYBOARD_STEP = 0.02

/**
 * Two resizable panes with a draggable divider.
 *
 * Deliberately dependency-free: pointer capture on the handle means the drag
 * keeps tracking even when the cursor outruns the 6px hit area or crosses into
 * the terminal, and a `separator` role with arrow-key support keeps the layout
 * reachable without a mouse.
 */
export function SplitPane({
  direction,
  first,
  second,
  fraction,
  onFractionChange,
  defaultFraction,
  label,
  className,
}: SplitPaneProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [dragging, setDragging] = useState(false)
  const horizontal = direction === 'horizontal'

  const fractionFromEvent = useCallback(
    (clientX: number, clientY: number): number | null => {
      const container = containerRef.current
      if (!container) return null
      const rect = container.getBoundingClientRect()
      const size = horizontal ? rect.width : rect.height
      if (size <= 0) return null
      const offset = horizontal ? clientX - rect.left : clientY - rect.top
      return clampFraction(offset / size)
    },
    [horizontal],
  )

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    // Ignore secondary buttons so a right-click never starts a phantom drag.
    if (event.button !== 0) return
    event.preventDefault()
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // A pointer that is no longer active throws NotFoundError. Dragging still
      // works from the handle itself, so this is not worth failing the gesture.
    }
    setDragging(true)
  }

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    const next = fractionFromEvent(event.clientX, event.clientY)
    if (next !== null) onFractionChange(next)
  }

  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    try {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
    } catch {
      // Same as capture: the pointer may already be gone.
    }
    setDragging(false)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const decrease = horizontal ? 'ArrowLeft' : 'ArrowUp'
    const increase = horizontal ? 'ArrowRight' : 'ArrowDown'

    if (event.key === decrease) {
      event.preventDefault()
      onFractionChange(clampFraction(fraction - KEYBOARD_STEP))
    } else if (event.key === increase) {
      event.preventDefault()
      onFractionChange(clampFraction(fraction + KEYBOARD_STEP))
    } else if (event.key === 'Home') {
      event.preventDefault()
      onFractionChange(clampFraction(0))
    } else if (event.key === 'End') {
      event.preventDefault()
      onFractionChange(clampFraction(1))
    } else if (event.key === 'Enter' && defaultFraction !== undefined) {
      event.preventDefault()
      onFractionChange(clampFraction(defaultFraction))
    }
  }

  // `h-full w-full` below is load bearing, not decoration. Both panes size
  // themselves as a percentage of this box, and a percentage against an `auto`
  // height resolves to `auto` too: the panes would then grow to fit their
  // content, the lesson would render at its full natural height, and the column
  // would overflow the window with nothing anywhere able to scroll it.
  return (
    <div
      ref={containerRef}
      className={cn(
        'flex h-full w-full min-h-0 min-w-0',
        horizontal ? 'flex-row' : 'flex-col',
        className,
      )}
    >
      <div
        className="flex min-h-0 min-w-0 flex-none overflow-hidden"
        style={horizontal ? { width: `${fraction * 100}%` } : { height: `${fraction * 100}%` }}
      >
        {first}
      </div>

      <div
        role="separator"
        tabIndex={0}
        aria-label={label}
        aria-orientation={horizontal ? 'vertical' : 'horizontal'}
        aria-valuenow={Math.round(fraction * 100)}
        aria-valuemin={12}
        aria-valuemax={88}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={handleKeyDown}
        onDoubleClick={
          defaultFraction === undefined
            ? undefined
            : () => onFractionChange(clampFraction(defaultFraction))
        }
        className={cn(
          'group relative z-10 flex-none touch-none bg-rule',
          'transition-colors duration-150 ease-paper',
          'focus-visible:bg-accent focus-visible:outline-none',
          horizontal ? 'w-px cursor-col-resize' : 'h-px cursor-row-resize',
          dragging ? 'bg-accent' : 'hover:bg-accent',
        )}
      >
        {/* A 1px border is the right look but a terrible target: this invisible
            strip widens the grab area to 9px without shifting the layout. */}
        <span
          aria-hidden
          className={cn(
            'absolute',
            horizontal ? '-inset-x-1 inset-y-0' : '-inset-y-1 inset-x-0',
          )}
        />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">{second}</div>
    </div>
  )
}
