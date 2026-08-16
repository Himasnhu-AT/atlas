import Link from 'next/link'

import { currentUser } from '@/lib/server/session'
import { AccountMenu } from './account-menu'

/**
 * The masthead.
 *
 * A hairline under it and nothing else: no shadow, no blur, no floating pill.
 * Navigation stays visible at every width rather than collapsing into a
 * hamburger, because there are three links and a phone has room for three links.
 */
export async function SiteHeader() {
  const user = await currentUser()

  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/92 backdrop-blur-[2px]">
      <div className="mx-auto flex h-16 w-full max-w-page items-center gap-6 px-6 sm:px-8">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center font-serif text-[17px] font-medium tracking-[-0.01em] text-ink"
        >
          Learn&thinsp;AI
        </Link>

        <nav aria-label="Main" className="flex items-center gap-5 text-caption sm:gap-7">
          <NavLink href="/learn">Curriculum</NavLink>
          <NavLink href="/download">Desktop</NavLink>
          {user && <NavLink href="/dashboard">Progress</NavLink>}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <AccountMenu displayName={user.displayName} email={user.email} />
          ) : (
            <>
              <Link
                href="/login"
                className="hidden min-h-11 items-center px-2 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink sm:inline-flex"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="inline-flex min-h-11 items-center rounded-field bg-ink px-4 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
              >
                Start
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

/**
 * A nav link draws a hairline under itself on hover, the same gesture the page
 * rules use, rather than only changing colour.
 */
function NavLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      href={href}
      className="group relative inline-flex min-h-11 items-center text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
    >
      {children}
      <span
        aria-hidden
        className="absolute inset-x-0 bottom-4 h-px origin-left scale-x-0 bg-accent transition-transform duration-200 ease-paper group-hover:scale-x-100"
      />
    </Link>
  )
}
