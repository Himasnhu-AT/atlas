import type { ComponentPropsWithRef, ReactNode } from 'react'
import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from 'lucide-react'
import { cn } from '../lib/cn'

export type AlertVariant = 'info' | 'success' | 'warning' | 'error'

export interface AlertProps extends Omit<ComponentPropsWithRef<'div'>, 'title'> {
  variant?: AlertVariant
  /** Bold first line. Shadows the DOM `title` attribute on purpose. */
  title?: ReactNode
  /** Replace the default variant icon; pass `null` to drop it entirely. */
  icon?: ReactNode | null
  /** Renders a dismiss button when provided. */
  onDismiss?: () => void
}

const VARIANTS: Record<AlertVariant, { shell: string; icon: string; Icon: typeof Info }> = {
  info: {
    shell: 'border-accent/25 bg-accent-wash',
    icon: 'text-accent',
    Icon: Info,
  },
  success: {
    shell: 'border-pass/30 bg-pass-wash',
    icon: 'text-pass',
    Icon: CircleCheck,
  },
  warning: {
    shell: 'border-warn/35 bg-warn-wash',
    icon: 'text-warn',
    Icon: TriangleAlert,
  },
  error: {
    shell: 'border-fail/30 bg-fail-wash',
    icon: 'text-fail',
    Icon: CircleAlert,
  },
}

/** Inline status message. Errors announce themselves assertively. */
export function Alert({
  variant = 'info',
  title,
  icon,
  onDismiss,
  className,
  children,
  ...props
}: AlertProps) {
  const config = VARIANTS[variant]
  const { Icon } = config

  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      aria-live={variant === 'error' ? 'assertive' : 'polite'}
      className={cn(
        'flex items-start gap-3 rounded-field border p-3.5 text-sm text-ink',
        config.shell,
        className,
      )}
      {...props}
    >
      {icon === null ? null : (
        <span className={cn('mt-px shrink-0 [&_svg]:size-[1.125rem]', config.icon)}>
          {icon ?? <Icon aria-hidden strokeWidth={2} />}
        </span>
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {title ? <p className="leading-snug font-semibold text-ink">{title}</p> : null}
        {children ? (
          <div className="leading-relaxed text-ink-soft [&_a]:font-medium [&_a]:text-accent [&_a]:underline [&_a]:underline-offset-2">
            {children}
          </div>
        ) : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className={cn(
            '-m-1 shrink-0 rounded-lg p-1 text-muted transition-colors duration-150',
            'hover:bg-paper-sunken hover:text-ink',
          )}
        >
          <X aria-hidden className="size-4" />
        </button>
      ) : null}
    </div>
  )
}
