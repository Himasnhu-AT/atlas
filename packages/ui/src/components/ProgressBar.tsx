import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '../lib/cn'

export type ProgressTone = 'brand' | 'success' | 'neutral'

export interface ProgressBarProps extends Omit<ComponentPropsWithRef<'div'>, 'children'> {
  value: number
  max?: number
  /** Rendered above the track; also becomes the accessible name. */
  label?: ReactNode
  tone?: ProgressTone
  size?: 'xs' | 'sm' | 'md'
  /** Show a `12 / 20` counter on the right of the label row. */
  showValue?: boolean
  /** Override the right-hand readout (defaults to `value / max`). */
  valueText?: string
}

const TONES: Record<ProgressTone, string> = {
  brand: 'bg-accent',
  success: 'bg-pass',
  neutral: 'bg-rule-strong',
}

const TRACK_SIZES = {
  xs: 'h-1',
  sm: 'h-1.5',
  md: 'h-2.5',
} as const

/** Determinate progress track with an optional label row. */
export function ProgressBar({
  value,
  max = 100,
  label,
  tone = 'brand',
  size = 'sm',
  showValue = false,
  valueText,
  className,
  ...props
}: ProgressBarProps) {
  const safeMax = max > 0 ? max : 100
  const clamped = Math.min(Math.max(value, 0), safeMax)
  const pct = (clamped / safeMax) * 100
  const readout = valueText ?? `${Math.round(clamped)} / ${Math.round(safeMax)}`
  const hasHeader = label !== undefined || showValue

  return (
    <div className={cn('flex w-full flex-col gap-1.5', className)} {...props}>
      {hasHeader ? (
        <div className="flex items-baseline justify-between gap-3 text-xs font-medium">
          <span className="truncate text-ink-soft">{label}</span>
          {showValue ? (
            <span className="shrink-0 tabular-nums text-muted">{readout}</span>
          ) : null}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuenow={clamped}
        aria-valuetext={readout}
        aria-label={typeof label === 'string' ? label : undefined}
        className={cn(
          'w-full overflow-hidden rounded-full bg-paper-sunken',
          'inset-shadow-[0_1px_1px_rgb(0_0_0/0.04)]',
          TRACK_SIZES[size],
        )}
      >
        <div
          className={cn(
            'h-full rounded-full transition-[width] duration-500 ease-paper',
            TONES[tone],
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
