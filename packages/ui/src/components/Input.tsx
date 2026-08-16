import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '../lib/cn'

export type InputSize = 'sm' | 'md' | 'lg'

export interface InputProps extends Omit<ComponentPropsWithRef<'input'>, 'size'> {
  /** Paints the error state and sets `aria-invalid`. */
  invalid?: boolean
  inputSize?: InputSize
  /** Icon rendered inside the field, before the text. */
  iconLeft?: ReactNode
  /** Icon or affordance rendered inside the field, after the text. */
  iconRight?: ReactNode
}

const SIZES: Record<InputSize, string> = {
  sm: 'h-8 rounded-lg px-2.5 text-[0.8125rem]',
  md: 'h-10 rounded-field px-3 text-sm',
  lg: 'h-12 rounded-field px-3.5 text-[0.9375rem]',
}

const PAD_LEFT: Record<InputSize, string> = { sm: 'pl-8', md: 'pl-10', lg: 'pl-11' }
const PAD_RIGHT: Record<InputSize, string> = { sm: 'pr-8', md: 'pr-10', lg: 'pr-11' }

/** Single-line text field, optionally wrapped with inline icons. */
export function Input({
  invalid = false,
  inputSize = 'md',
  iconLeft,
  iconRight,
  className,
  disabled,
  ...props
}: InputProps) {
  const field = (
    <input
      disabled={disabled}
      aria-invalid={invalid || undefined}
      className={cn(
        'w-full border bg-paper-raised text-ink shadow-none transition-[border-color,box-shadow,background-color]',
        'duration-150 ease-paper outline-none',
        'placeholder:text-muted',
        'disabled:cursor-not-allowed disabled:bg-paper-sunken disabled:text-muted',
        'focus-visible:outline-2 focus-visible:outline-offset-0',
        invalid
          ? 'border-fail focus-visible:outline-fail'
          : 'border-rule hover:border-rule-strong focus-visible:border-accent focus-visible:outline-accent',
        SIZES[inputSize],
        iconLeft && PAD_LEFT[inputSize],
        iconRight && PAD_RIGHT[inputSize],
        className,
      )}
      {...props}
    />
  )

  if (!iconLeft && !iconRight) return field

  return (
    <div className="relative flex w-full items-center">
      {iconLeft ? (
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute left-3 flex items-center text-muted',
            '[&_svg]:size-4',
            inputSize === 'sm' && 'left-2.5',
          )}
        >
          {iconLeft}
        </span>
      ) : null}
      {field}
      {iconRight ? (
        <span
          className={cn(
            'absolute right-3 flex items-center text-muted',
            '[&_svg]:size-4',
            inputSize === 'sm' && 'right-2.5',
          )}
        >
          {iconRight}
        </span>
      ) : null}
    </div>
  )
}
