import type { ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'

export interface CardProps extends ComponentPropsWithRef<'div'> {
  /** Adds hover elevation + pointer affordance for clickable cards. */
  interactive?: boolean
  /** `flat` drops the shadow, for cards nested inside other surfaces. */
  elevation?: 'flat' | 'raised'
}

/** The surface primitive: a bordered panel that sits above the page canvas. */
export function Card({
  interactive = false,
  elevation = 'raised',
  className,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-sheet border border-rule bg-paper-raised text-ink',
        elevation === 'raised' && 'shadow-none',
        interactive &&
          'cursor-pointer transition-[box-shadow,border-color,transform] duration-200 ease-paper ' +
            'hover:-translate-y-0.5 hover:border-rule-strong hover:shadow-none ' +
            'focus-visible:-translate-y-0.5 focus-visible:shadow-none',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: ComponentPropsWithRef<'div'>) {
  return <div className={cn('flex flex-col gap-1.5 p-5 pb-0', className)} {...props} />
}

export function CardTitle({ className, ...props }: ComponentPropsWithRef<'h3'>) {
  return (
    <h3
      className={cn('text-base leading-snug font-semibold tracking-[-0.01em] text-ink', className)}
      {...props}
    />
  )
}

export function CardDescription({ className, ...props }: ComponentPropsWithRef<'p'>) {
  return <p className={cn('text-sm leading-relaxed text-ink-soft', className)} {...props} />
}

export function CardContent({ className, ...props }: ComponentPropsWithRef<'div'>) {
  return <div className={cn('p-5', className)} {...props} />
}

export function CardFooter({ className, ...props }: ComponentPropsWithRef<'div'>) {
  return (
    <div
      className={cn('flex items-center gap-3 border-t border-rule px-5 py-3.5', className)}
      {...props}
    />
  )
}
