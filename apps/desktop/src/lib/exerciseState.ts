/**
 * How the work on disk relates to the exercise that was just written over it.
 *
 * `changed` is the case worth having. The app refreshes an exercise's support
 * files on every open and never overwrites `solution.py`. Both rules are right,
 * and together they leave one bad case: a rewritten exercise lands on top of a
 * solution written against the old one, and the learner meets an `ImportError`
 * naming a symbol the lesson just told them to write. That is the one failure
 * this course promises them is never their own logic, so it gets said out loud.
 *
 * `unknown` is a workspace written before stamping existed. It is its own state
 * rather than being folded into `restored`, because claiming an exercise has not
 * moved when there is no way to tell is the kind of small lie that costs
 * somebody an afternoon.
 *
 * This lives apart from `exercise.ts` for one reason: that module reaches the
 * Tauri IPC bridge at import time, so nothing in it can be executed outside the
 * app. This function is pure and has no imports, so the decision table below can
 * be run and checked. The decision is worth more than the file boundary costs.
 */
export type ExerciseState = 'fresh' | 'restored' | 'changed' | 'unknown'

export interface ExerciseStateInput {
  /** Whether `solution.py` was already on disk before this open. */
  hasSolution: boolean
  /** The stamp left by the previous open, if there was one. */
  previousStamp: string | undefined
  /** The hash of the exercise files this build just wrote. */
  currentHash: string | undefined
}

export function exerciseState({
  hasSolution,
  previousStamp,
  currentHash,
}: ExerciseStateInput): ExerciseState {
  // Nothing of theirs was here, so nothing of theirs can be stale.
  if (!hasSolution) return 'fresh'
  // Work was already here. Whether it still matches the exercise is the
  // question, and without both a stamp and a hash there is no honest answer.
  if (previousStamp === undefined || currentHash === undefined) return 'unknown'
  return previousStamp === currentHash ? 'restored' : 'changed'
}
