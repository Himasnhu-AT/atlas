import Link from 'next/link'

export default function NotFound() {
  return (
    <main
      id="main"
      className="mx-auto flex min-h-screen w-full max-w-page flex-col justify-center px-6 sm:px-8"
    >
      <p className="text-eyebrow font-medium uppercase text-muted">404</p>
      <h1 className="mt-4 max-w-[18ch] text-title text-ink">
        This page is not in the book.
      </h1>
      <p className="mt-5 max-w-[52ch] font-serif text-lead text-ink-soft">
        The link may be wrong, or the page may have moved. The curriculum is the best place to
        pick the thread back up.
      </p>

      <div className="mt-9 flex flex-wrap items-center gap-x-7 gap-y-3">
        <Link
          href="/learn"
          className="inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
        >
          Curriculum
        </Link>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
        >
          Home
        </Link>
      </div>
    </main>
  )
}
