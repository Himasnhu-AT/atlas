import { FileClock } from 'lucide-react'

/**
 * Shown when the exercise changed since the learner last worked on it.
 *
 * The app refreshes `test.py` and the scaffold on every open and never touches
 * `solution.py`. Both rules are right and together they leave one bad case: work
 * written against the old exercise meets the new test, and the first thing the
 * learner sees is an `ImportError` naming a symbol the lesson just told them to
 * write. Every other lesson in this course tells them that failure is never
 * their own logic, so this says what actually happened instead of letting them
 * debug code that was correct yesterday.
 *
 * It offers the new scaffold and does not take it. Their work is on disk and
 * replacing it is their call, which is the same rule the reset button follows.
 */
export function ExerciseMovedBanner({
  onUseScaffold,
  onDismiss,
}: {
  onUseScaffold: () => void
  onDismiss: () => void
}) {
  return (
    <div className="flex shrink-0 items-center gap-2.5 border-b border-warn/35 bg-warn-wash px-3 py-1.5 text-xs">
      <FileClock aria-hidden className="size-4 shrink-0 text-warn" />
      <p className="min-w-0 text-ink-soft">
        <span className="font-semibold text-ink">This exercise was updated.</span> Its tests and
        scaffold have changed since you last opened it, so your saved code may not match what the
        tests now import. Your work has not been touched.
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onUseScaffold}
          className="rounded-field px-2 py-1 font-medium text-ink-soft transition-colors duration-150 hover:bg-warn/10 hover:text-ink"
        >
          Start from the new scaffold
        </button>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-field px-2 py-1 font-medium text-ink-soft transition-colors duration-150 hover:bg-warn/10 hover:text-ink"
        >
          Keep my code
        </button>
      </div>
    </div>
  )
}
