import type { ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'

export type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg'

export interface SpinnerProps extends ComponentPropsWithRef<'span'> {
  size?: SpinnerSize
  /**
   * Announced to screen readers. Pass `null` for decorative spinners that sit
   * inside an already-labelled control (a loading button, for instance).
   */
  label?: string | null
}

const SIZES: Record<SpinnerSize, string> = {
  xs: 'size-3 border-[1.5px]',
  sm: 'size-4 border-2',
  md: 'size-5 border-2',
  lg: 'size-8 border-[3px]',
}

/** Indeterminate activity indicator. */
export function Spinner({ size = 'md', label = 'Loading', className, ...props }: SpinnerProps) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-live={label ? 'polite' : undefined}
      aria-hidden={label ? undefined : true}
      className={cn('inline-flex items-center gap-2 text-ink-soft', className)}
      {...props}
    >
      <span
        className={cn(
          'inline-block shrink-0 animate-spin rounded-full border-current/25 border-t-current',
          SIZES[size],
        )}
      />
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  )
}
