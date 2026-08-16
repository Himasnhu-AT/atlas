import { useEffect, useId, useRef } from 'react'
import { Button } from '@learn/ui'
import type { ButtonVariant } from '@learn/ui'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  confirmVariant?: ButtonVariant
  onConfirm: () => void
  onCancel: () => void
}

/**
 * A modal confirm. `window.confirm` is blocked in some webview configurations
 * and looks foreign inside a Tauri window, so destructive actions use this.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancel',
  confirmVariant = 'primary',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId()
  const descriptionId = useId()
  const confirmRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!open) return
    confirmRef.current?.focus()

    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCancel()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <button
        type="button"
        aria-label="Cancel"
        onClick={onCancel}
        className="absolute inset-0 animate-fade-in bg-ink/50 backdrop-blur-[2px]"
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative w-full max-w-md animate-rise-in rounded-sheet border border-rule bg-paper-raised p-5 shadow-none"
      >
        <h2 id={titleId} className="text-base font-semibold text-ink">
          {title}
        </h2>
        <p id={descriptionId} className="mt-2 text-sm leading-relaxed text-ink-soft">
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button ref={confirmRef} variant={confirmVariant} size="sm" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
