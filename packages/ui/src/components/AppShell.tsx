'use client'

import { useCallback, useEffect, useState, type MouseEvent, type ReactNode } from 'react'
import { Menu, X } from 'lucide-react'
import { cn } from '../lib/cn'

export interface AppShellProps {
  /** Top bar contents — branding, breadcrumbs, account menu. */
  header: ReactNode
  /** Optional left rail. Becomes a slide-over drawer below `lg`. */
  sidebar?: ReactNode
  children: ReactNode
  className?: string
  /** Applied to the scrolling `<main>` element. */
  contentClassName?: string
}

const SIDEBAR_WIDTH = 'w-72'

/**
 * The application frame: fixed header, optional sidebar, one scroll container
 * for content. Sized with `h-dvh` so it behaves the same in the browser and in
 * the desktop shell, where the window — not the page — is the viewport.
 */
export function AppShell({
  header,
  sidebar,
  children,
  className,
  contentClassName,
}: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  useEffect(() => {
    if (!drawerOpen) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDrawer()
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [drawerOpen, closeDrawer])

  // Any activation inside the drawer means the user navigated — get out of the way.
  const handleDrawerClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target
    if (target instanceof Element && target.closest('a, button')) closeDrawer()
  }

  return (
    <div className={cn('flex h-dvh flex-col overflow-hidden bg-paper text-ink', className)}>
      <header
        className={cn(
          'z-30 flex h-14 shrink-0 items-center gap-3 border-b border-rule px-3 sm:px-4',
          'bg-paper-raised/85 backdrop-blur-md backdrop-saturate-150',
        )}
      >
        {sidebar ? (
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open lesson navigation"
            aria-expanded={drawerOpen}
            className={cn(
              'inline-flex size-9 shrink-0 items-center justify-center rounded-field',
              'text-ink-soft transition-colors duration-150 ease-paper',
              'hover:bg-paper-sunken hover:text-ink lg:hidden',
            )}
          >
            <Menu aria-hidden className="size-5" />
          </button>
        ) : null}
        <div className="flex min-w-0 flex-1 items-center gap-3">{header}</div>
      </header>

      <div className="flex min-h-0 flex-1">
        {sidebar ? (
          <aside
            className={cn(
              'hidden shrink-0 border-r border-rule bg-paper-raised lg:flex lg:flex-col',
              SIDEBAR_WIDTH,
            )}
          >
            {sidebar}
          </aside>
        ) : null}

        <main className={cn('min-w-0 flex-1 overflow-y-auto', contentClassName)}>{children}</main>
      </div>

      {sidebar && drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close lesson navigation"
            onClick={closeDrawer}
            className="absolute inset-0 animate-fade-in bg-ink/45 backdrop-blur-[2px]"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Lesson navigation"
            onClick={handleDrawerClick}
            className={cn(
              'absolute inset-y-0 left-0 flex animate-slide-in-left flex-col',
              'border-r border-rule bg-paper-raised shadow-none',
              SIDEBAR_WIDTH,
            )}
          >
            <div className="flex h-14 shrink-0 items-center justify-end border-b border-rule px-2">
              <button
                type="button"
                onClick={closeDrawer}
                aria-label="Close lesson navigation"
                className={cn(
                  'inline-flex size-9 items-center justify-center rounded-field text-ink-soft',
                  'transition-colors duration-150 hover:bg-paper-sunken hover:text-ink',
                )}
              >
                <X aria-hidden className="size-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">{sidebar}</div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
