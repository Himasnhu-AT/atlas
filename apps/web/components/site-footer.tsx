import Link from 'next/link'

import { storageMode } from '@/lib/server/store'

export function SiteFooter() {
  const local = storageMode() === 'local'

  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex w-full max-w-page flex-wrap items-baseline gap-x-7 gap-y-3 px-6 py-10 text-caption text-muted sm:px-8">
        <span className="inline-flex min-h-11 items-center font-serif text-ink">Learn&thinsp;AI</span>
        <Link
          href="/learn"
          className="inline-flex min-h-11 items-center transition-colors duration-200 ease-paper hover:text-ink"
        >
          Curriculum
        </Link>
        <Link
          href="/download"
          className="inline-flex min-h-11 items-center transition-colors duration-200 ease-paper hover:text-ink"
        >
          Desktop app
        </Link>

        {local && (
          <span className="sm:ml-auto">
            Local storage mode. Accounts live in <code>.data/store.json</code>.
          </span>
        )}
      </div>
    </footer>
  )
}
