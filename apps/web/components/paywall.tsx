import Link from 'next/link'

/**
 * What a locked lesson shows instead of its body.
 *
 * A ruled row, not a modal. A modal over content the reader can see behind it
 * is an argument with them, and the content is not there to see anyway: the
 * server never sent it.
 *
 * The title, the summary and the whole table of contents are still on the page.
 * Somebody deciding whether to pay has to be able to see what they would be
 * paying for, and a locked list of lesson names is a worse advert than an open
 * one.
 */
export function Paywall({ courseName, signedIn }: { courseName: string; signedIn: boolean }) {
  return (
    <div className="my-4 border-y-2 border-ink py-10">
      <p className="text-eyebrow font-medium uppercase text-muted">Members only</p>

      <p className="mt-4 max-w-[52ch] font-serif text-lead text-ink">
        The first track of every course is free, and this lesson is past it.
      </p>

      <p className="mt-4 max-w-[56ch] text-ink-soft">
        Membership opens every module of {courseName} and of every other course, on the web and
        in the practice app. Everything you have finished so far stays yours either way.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
        {/* Deliberately not a checkout. There is nothing to buy yet, and a
            button that goes nowhere is worse than an honest sentence. */}
        <Link
          href="/learn"
          className="inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
        >
          Back to the courses
        </Link>

        {!signedIn && (
          <Link
            href="/signup"
            className="inline-flex min-h-11 items-center text-caption text-accent-deep underline underline-offset-2"
          >
            Make an account
          </Link>
        )}
      </div>
    </div>
  )
}
