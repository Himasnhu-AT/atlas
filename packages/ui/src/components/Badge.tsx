import type { ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'

export type BadgeVariant =
  | 'neutral'
  | 'brand'
  | 'success'
  | 'warning'
  | 'danger'
  | 'outline'

export type BadgeSize = 'sm' | 'md'

export interface BadgeProps extends ComponentPropsWithRef<'span'> {
  variant?: BadgeVariant
  size?: BadgeSize
  /** Renders a small leading dot in the badge's own colour. */
  dot?: boolean
}

const VARIANTS: Record<BadgeVariant, string> = {
  neutral: 'border-transparent bg-paper-sunken text-ink-soft',
  brand: 'border-transparent bg-accent-wash text-accent',
  success: 'border-transparent bg-pass-wash text-pass',
  warning: 'border-transparent bg-warn-wash text-warn',
  danger: 'border-transparent bg-fail-wash text-fail',
  outline: 'border-rule bg-transparent text-ink-soft',
}

const SIZES: Record<BadgeSize, string> = {
  sm: 'h-5 px-2 text-[0.6875rem]',
  md: 'h-6 px-2.5 text-xs',
}

/** Compact status/metadata pill. */
export function Badge({
  variant = 'neutral',
  size = 'md',
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium ' +
          'tracking-[0.01em] whitespace-nowrap',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {dot ? <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-current" /> : null}
      {children}
    </span>
  )
}
