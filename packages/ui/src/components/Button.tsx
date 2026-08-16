import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ComponentPropsWithRef<'button'> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Swaps the leading icon for a spinner and blocks interaction. */
  loading?: boolean
  fullWidth?: boolean
  /** Square padding for a single-glyph button. */
  iconOnly?: boolean
  iconLeft?: ReactNode
  iconRight?: ReactNode
}

const BASE =
  'relative inline-flex shrink-0 items-center justify-center gap-2 border font-medium leading-none ' +
  'whitespace-nowrap select-none transition-[background-color,border-color,color,box-shadow,opacity] ' +
  'duration-150 ease-paper active:translate-y-px ' +
  'disabled:pointer-events-none disabled:opacity-50 disabled:active:translate-y-0'

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'border-transparent bg-accent text-white shadow-none ' +
    'hover:bg-accent-deep active:bg-accent-deep',
  secondary:
    'border-rule bg-paper-raised text-ink shadow-none ' +
    'hover:border-rule-strong hover:bg-paper-sunken active:bg-paper-sunken',
  ghost:
    'border-transparent bg-transparent text-ink-soft ' +
    'hover:bg-paper-sunken hover:text-ink active:bg-paper-sunken',
  danger:
    'border-transparent bg-fail text-white shadow-none ' +
    'hover:bg-fail-deep active:bg-fail-deep',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 rounded-lg px-3 text-[0.8125rem] [&_svg]:size-4',
  md: 'h-10 rounded-field px-4 text-sm [&_svg]:size-[1.05rem]',
  lg: 'h-12 rounded-field px-6 text-[0.9375rem] [&_svg]:size-5',
}

const ICON_ONLY_SIZES: Record<ButtonSize, string> = {
  sm: 'w-8 px-0',
  md: 'w-10 px-0',
  lg: 'w-12 px-0',
}

/**
 * The one button in the system. Everything else — links styled as buttons,
 * toolbar actions — should reach for a variant rather than a new component.
 */
export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  iconOnly = false,
  iconLeft,
  iconRight,
  disabled,
  className,
  children,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        BASE,
        VARIANTS[variant],
        SIZES[size],
        iconOnly && ICON_ONLY_SIZES[size],
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {loading ? (
        <Spinner size={size === 'lg' ? 'md' : 'sm'} label={null} className="text-current" />
      ) : (
        iconLeft
      )}
      {children}
      {loading ? null : iconRight}
    </button>
  )
}
