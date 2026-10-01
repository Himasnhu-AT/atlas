import type { ChallengeKind } from '@atlas/core'

import type { ChallengeRenderer } from './protocol'
import { Assign } from './kinds/Assign'
import { Blanks } from './kinds/Blanks'
import { Choice } from './kinds/Choice'
import { Custom } from './kinds/Custom'
import { Machine } from './kinds/Machine'
import { Numeric } from './kinds/Numeric'
import { Order } from './kinds/Order'
import { Spot } from './kinds/Spot'
import { TextContract } from './kinds/TextContract'
import { Tune } from './kinds/Tune'

/**
 * Every kind, and the component that draws it.
 *
 * `satisfies Record<ChallengeKind, ...>` is the whole point of the file. A kind
 * added to `CHALLENGE_KINDS` with no renderer is a `pnpm typecheck` failure
 * here rather than an empty panel a learner finds partway through a lesson.
 * The repo already carries hand-maintained widget lists that disagree with each
 * other, and this is the shape that cannot.
 */
export const KindRenderers = {
  choice: Choice,
  order: Order,
  assign: Assign,
  blanks: Blanks,
  numeric: Numeric,
  'text-contract': TextContract,
  machine: Machine,
  tune: Tune,
  spot: Spot,
  custom: Custom,
} satisfies Record<ChallengeKind, ChallengeRenderer<any>>
