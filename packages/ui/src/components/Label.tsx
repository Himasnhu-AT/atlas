import type { ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'

export interface LabelProps extends ComponentPropsWithRef<'label'> {
  /** Appends a required marker that is also announced to screen readers. */
  required?: boolean
  /** Muted helper line rendered under the label text. */
  hint?: string
}

/** Form field label. Pair with `Input` via `htmlFor`. */
export function Label({ required = false, hint, className, children, ...props }: LabelProps) {
  return (
    <label className={cn('flex flex-col gap-1', className)} {...props}>
      <span className="text-sm leading-none font-medium text-ink">
        {children}
        {required ? (
          <span className="ml-0.5 text-fail">
            <span aria-hidden>*</span>
            <span className="sr-only">(required)</span>
          </span>
        ) : null}
      </span>
      {hint ? <span className="text-xs leading-snug text-muted">{hint}</span> : null}
    </label>
  )
}
