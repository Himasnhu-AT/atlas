import Link from 'next/link'

export function SiteFooter() {
  return (
    <footer className="border-t border-rule">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-baseline gap-x-7 gap-y-3 px-6 py-10 text-caption text-muted sm:px-8">
        <span className="inline-flex min-h-11 items-center font-serif text-ink">Atlas</span>
        <Link
          href="/learn"
          className="inline-flex min-h-11 items-center transition-colors duration-200 ease-paper hover:text-ink"
        >
          Courses
        </Link>
        <Link
          href="/atlas"
          className="inline-flex min-h-11 items-center transition-colors duration-200 ease-paper hover:text-ink"
        >
          Curriculum Roadmap
        </Link>
        <Link
          href="/download"
          className="inline-flex min-h-11 items-center transition-colors duration-200 ease-paper hover:text-ink"
        >
          Desktop app
        </Link>
      </div>
    </footer>
  )
}
