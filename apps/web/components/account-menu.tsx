'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'

/**
 * The account popover.
 *
 * Deliberately not `role="menu"`. That role promises arrow-key navigation and
 * managed focus between menuitems, and a popover holding two controls does not
 * need either. Claiming the role without honouring it is worse for a screen
 * reader than not claiming it: it announces a menu that does not behave like
 * one. This is a disclosure with a link and a button inside, which is what it
 * actually is.
 */
export function AccountMenu({
  displayName,
  email,
  isAdmin = false,
}: {
  displayName: string
  email: string
  isAdmin?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const router = useRouter()

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: PointerEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setOpen(false)
      // Escape must hand focus back, or a keyboard user is stranded at the top
      // of the document with no idea where they were.
      trigger.current?.focus()
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  async function signOut() {
    setSigningOut(true)
    await fetch('/api/auth/logout', { method: 'POST' })
    router.push('/')
    // Re-runs the server components so the masthead reflects the new state;
    // push alone would leave a cached signed-in shell.
    router.refresh()
  }

  return (
    <div ref={container} className="relative">
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={`Account: ${displayName}`}
        className="inline-flex size-11 items-center justify-center rounded-full border border-rule-strong text-caption font-medium text-ink transition-colors duration-200 ease-paper hover:bg-paper-raised"
      >
        <span aria-hidden>{displayName.slice(0, 1).toUpperCase() || '?'}</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-60 overflow-hidden rounded-sheet border border-rule bg-paper-raised shadow-sm">
          <div className="border-b border-rule px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="truncate text-caption font-medium text-ink">{displayName}</p>
              {isAdmin && (
                <span className="rounded bg-ink px-1.5 py-0.5 text-[9px] font-mono uppercase text-paper">
                  Admin
                </span>
              )}
            </div>
            <p className="truncate text-caption text-muted">{email}</p>
          </div>
          {isAdmin && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className="block border-b border-rule px-4 py-3 text-caption font-medium text-ink transition-colors duration-200 ease-paper hover:bg-paper-sunken"
            >
              Admin portal
            </Link>
          )}
          <Link
            href="/account/devices"
            onClick={() => setOpen(false)}
            className="block px-4 py-3 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:bg-paper-sunken hover:text-ink"
          >
            Devices
          </Link>
          <button
            type="button"
            onClick={signOut}
            disabled={signingOut}
            className="w-full border-t border-rule px-4 py-3 text-left text-caption text-ink-soft transition-colors duration-200 ease-paper hover:bg-paper-sunken hover:text-ink disabled:opacity-60"
          >
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  )
}
