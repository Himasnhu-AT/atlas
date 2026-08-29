import type { Challenge, Verdict } from '@atlas/core'

/**
 * What every challenge renderer is handed, and all it is allowed to do.
 *
 * Renderers collect an answer and report a verdict. They do not draw the
 * verdict banner, own the hints, or decide when to advance: the runner does
 * all of that, so every challenge in the catalogue behaves the same way and a
 * new kind cannot invent its own idea of what passing looks like.
 */
export interface ChallengeRendererProps<C extends Challenge = Challenge> {
  challenge: C
  /** Opaque to the runner, persisted verbatim, shaped by the kind. */
  answer: unknown
  onAnswer: (answer: unknown) => void
  /**
   * For a kit kind the runner checks the answer itself. A `custom` component
   * owns its simulation, so it reports its own result through this.
   */
  onVerdict?: (verdict: Verdict) => void
  /** The last verdict, so a renderer can mark the specific thing that was wrong. */
  verdict: Verdict | null
  /** Solved. Renderers go read-only rather than disappearing. */
  settled: boolean
}

export type ChallengeRenderer<C extends Challenge = Challenge> = (
  props: ChallengeRendererProps<C>,
) => React.ReactNode
