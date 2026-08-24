import Link from 'next/link'

/**
 * What a module you have not reached shows instead of its body.
 *
 * A ruled row, not a modal. A modal over content the reader can see behind it
 * is an argument with them, and the content is not there to see anyway: the
 * server never sent it.
 *
 * It names the one thing to do next and links straight to it. A lock that only
 * says no is a dead end; a lock that says where the key is is a signpost, and
 * this is a course rather than a vault.
 */
export function Locked({
  blockedBy,
  courseSlug,
  signedIn,
}: {
  /** The direct prerequisites still outstanding, nearest first. */
  blockedBy: { name: string; slug: string }[]
  courseSlug: string
  signedIn: boolean
}) {
  const next = blockedBy[0]

  return (
    <div className="my-4 border-y-2 border-ink py-10">
      <p className="text-eyebrow font-medium uppercase text-muted">Not yet</p>

      <p className="mt-4 max-w-[52ch] font-serif text-lead text-ink">
        {blockedBy.length === 1
          ? `This one opens once you have finished ${blockedBy[0]!.name}.`
          : `This one opens once you have finished ${blockedBy
              .map((module) => module.name)
              .join(' and ')}.`}
      </p>

      <p className="mt-4 max-w-[56ch] text-ink-soft">
        {signedIn
          ? 'The order is not decoration. Each module is written assuming the one before it, and starting in the middle mostly teaches you that you started in the middle.'
          : 'Progress is kept against your account, so finishing a module needs one. Everything up to here is open without.'}
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
        {next && (
          <Link
            href={`/learn/${courseSlug}/${next.slug}`}
            className="inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
          >
            Go to {next.name}
          </Link>
        )}

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
