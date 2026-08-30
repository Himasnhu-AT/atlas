import { z } from 'zod'

import { Rule } from './rules'

/**
 * The closed set of things a learner can be asked to do in stage 1.
 *
 * Nine data-driven kinds and one escape hatch. The count is deliberate: the
 * catalogue has 122 lessons across AI agents, quantitative trading, systems
 * programming and data engineering, and a component per lesson is 122
 * components. Every kind here is authored as YAML in a lesson's frontmatter and
 * checked by a pure function in `check.ts`.
 *
 * `context` being shared across all of them is what keeps this at nine rather
 * than fifteen: "predict what this join returns" is a `choice` with a table
 * attached, not a `table-query` kind.
 */

const cid = z.string().regex(/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/, 'ids are lowercase kebab-case')

/** Read-only material the challenge is posed against. */
export const ChallengeContext = z.discriminatedUnion('as', [
  z.object({ as: z.literal('prose'), text: z.string().max(2000) }),
  z.object({
    as: z.literal('code'),
    lang: z.string().max(20).default('text'),
    source: z.string().max(4000),
  }),
  z.object({ as: z.literal('log'), lines: z.array(z.string().max(300)).min(1).max(40) }),
  z.object({
    as: z.literal('table'),
    caption: z.string().max(120).optional(),
    columns: z.array(z.string().max(40)).min(1).max(8),
    rows: z.array(z.array(z.union([z.string(), z.number(), z.boolean(), z.null()]))).min(1).max(30),
  }),
  z.object({
    as: z.literal('pairs'),
    items: z.array(z.object({ k: z.string().max(40), v: z.string().max(160) })).min(1).max(12),
  }),
])
export type ChallengeContext = z.infer<typeof ChallengeContext>

/**
 * What every challenge carries, and all of it is required.
 *
 * A challenge with no hints is a wall, and one with no `reveal` teaches nothing
 * the moment it is solved. Making either optional is how 400 challenges quietly
 * become a quiz.
 */
const Base = z.object({
  id: cid,
  prompt: z.string().min(1).max(400),
  context: ChallengeContext.optional(),
  /** Escalating. The first is a nudge, the last is nearly the answer. */
  hints: z.array(z.string().min(1).max(400)).min(1).max(3),
  /** Shown once solved, or once the hints run out. The one place it teaches. */
  reveal: z.string().min(1).max(600),
})

export const ChoiceChallenge = Base.extend({
  kind: z.literal('choice'),
  multiple: z.boolean().default(false),
  options: z
    .array(
      z.object({
        id: cid,
        label: z.string().min(1).max(240),
        correct: z.boolean().default(false),
        /** Why this option is what it is. Shown on selection, right or wrong. */
        note: z.string().min(1).max(300),
      }),
    )
    .min(2)
    .max(6),
})

export const OrderChallenge = Base.extend({
  kind: z.literal('order'),
  items: z.array(z.object({ id: cid, label: z.string().min(1).max(160) })).min(3).max(8),
  /** The one correct order, as item ids. Checked to be a permutation. */
  solution: z.array(cid).min(3).max(8),
  /** Per item, why it sits where it does. Surfaced when it is misplaced. */
  because: z.record(z.string(), z.string().max(240)).default({}),
})

export const AssignChallenge = Base.extend({
  kind: z.literal('assign'),
  buckets: z
    .array(z.object({ id: cid, label: z.string().max(80), note: z.string().max(200).optional() }))
    .min(2)
    .max(4),
  items: z
    .array(
      z.object({
        id: cid,
        label: z.string().max(160),
        bucket: cid,
        because: z.string().max(240).optional(),
      }),
    )
    .min(3)
    .max(12),
})

export const BlanksChallenge = Base.extend({
  kind: z.literal('blanks'),
  lang: z.string().max(20).default('text'),
  /** `{{1}}` marks blank one. Every blank must appear exactly once. */
  template: z.string().min(1).max(3000),
  blanks: z
    .array(
      z.object({
        n: z.number().int().positive().max(6),
        as: z.enum(['select', 'type']).default('select'),
        /** `select` only, and it must include a correct answer. */
        options: z.array(z.string().max(80)).max(6).default([]),
        /** Trimmed and case-folded against each of these. */
        accept: z.array(z.string().min(1).max(120)).min(1),
        note: z.string().max(240).optional(),
      }),
    )
    .min(1)
    .max(6),
})

export const NumericChallenge = Base.extend({
  kind: z.literal('numeric'),
  answer: z.number(),
  tolerance: z.number().nonnegative().default(0),
  unit: z.string().max(16).optional(),
  /** For an answer out by more than 10x: a wrong quantity, not wrong arithmetic. */
  scaleHint: z.string().max(240).optional(),
})

export const TextContractChallenge = Base.extend({
  kind: z.literal('text-contract'),
  lang: z.string().max(20).default('json'),
  /** What the learner starts from. The build proves it fails at least one rule. */
  initial: z.string().max(4000),
  /** Evaluated in order. The first failure is the feedback. */
  rules: z.array(Rule).min(1).max(12),
  /** A worked answer. The build proves it passes every rule. */
  solution: z.string().max(4000),
})

const VarTest = z.object({
  var: z.string().max(24),
  cmp: z.enum(['lt', 'lte', 'eq', 'gte', 'gt']),
  value: z.number(),
})

export const MachineChallenge = Base.extend({
  kind: z.literal('machine'),
  initial: cid,
  /** Named counters. The only state besides which node is current. */
  vars: z.record(z.string(), z.number()).default({}),
  states: z.record(
    z.string(),
    z.object({
      label: z.string().max(60),
      note: z.string().max(240).optional(),
      terminal: z.boolean().default(false),
      error: z.boolean().default(false),
    }),
  ),
  transitions: z
    .array(
      z.object({
        from: cid,
        on: z.string().min(1).max(40),
        to: cid,
        /** All must hold, or the action is not offered. */
        when: z.array(VarTest).default([]),
        effects: z
          .array(z.object({ var: z.string().max(24), op: z.enum(['set', 'inc', 'dec']), value: z.number() }))
          .default([]),
        note: z.string().max(240).optional(),
      }),
    )
    .min(1)
    .max(24),
  /**
   * `drive` picks actions until the goal holds. `predict` asks for the
   * resulting state before each action is applied; a wrong prediction shows the
   * transition's note and the machine still advances, so a run is never stuck.
   */
  mode: z.enum(['drive', 'predict']).default('drive'),
  win: z.object({
    state: cid.optional(),
    maxSteps: z.number().int().positive().max(30).default(12),
    requires: z.array(VarTest).default([]),
  }),
})

/** A term is `coef` times the product of the values it names. `of: []` is a constant. */
const Term = z.object({ coef: z.number().default(1), of: z.array(z.string().max(24)).max(3).default([]) })

export const TuneChallenge = Base.extend({
  kind: z.literal('tune'),
  inputs: z
    .array(
      z.object({
        id: cid,
        label: z.string().max(60),
        unit: z.string().max(16).optional(),
        min: z.number(),
        max: z.number(),
        step: z.number().positive().default(1),
        initial: z.number(),
      }),
    )
    .min(1)
    .max(4),
  outputs: z
    .array(
      z.object({
        id: cid,
        label: z.string().max(60),
        unit: z.string().max(16).optional(),
        /** May name inputs and outputs declared before it. Checked acyclic. */
        terms: z.array(Term).min(1).max(6),
        /** The window to land inside. Absent means shown but not graded. */
        target: z.object({ min: z.number().optional(), max: z.number().optional() }).optional(),
        note: z.string().max(240).optional(),
      }),
    )
    .min(1)
    .max(3),
})

export const SpotChallenge = Base.extend({
  kind: z.literal('spot'),
  lang: z.string().max(20).default('text'),
  source: z.string().min(1).max(3000),
  /** Zero-based indices of the offending lines. */
  targets: z.array(z.number().int().nonnegative()).min(1).max(6),
  requireAll: z.boolean().default(true),
  /** Line index to why that one is innocent. Turns a wrong click into a lesson. */
  decoys: z.record(z.string(), z.string().max(240)).default({}),
})

/**
 * A bespoke component, addressed through the same door as everything else.
 *
 * The kit covers the great majority of lessons. Some concepts are genuinely
 * visual and their state space cannot be enumerated in YAML: struct padding
 * under field reordering, a depth ladder matching on price and time. Those keep
 * their own component and are still authored, validated and sequenced like any
 * other challenge.
 */
export const CustomChallenge = Base.extend({
  kind: z.literal('custom'),
  component: z.string().min(1).max(60),
  /** Validated in a second pass against that component's own schema. */
  props: z.record(z.string(), z.any()).default({}),
})

export const Challenge = z.discriminatedUnion('kind', [
  ChoiceChallenge,
  OrderChallenge,
  AssignChallenge,
  BlanksChallenge,
  NumericChallenge,
  TextContractChallenge,
  MachineChallenge,
  TuneChallenge,
  SpotChallenge,
  CustomChallenge,
])
export type Challenge = z.infer<typeof Challenge>

export type ChoiceChallenge = z.infer<typeof ChoiceChallenge>
export type OrderChallenge = z.infer<typeof OrderChallenge>
export type AssignChallenge = z.infer<typeof AssignChallenge>
export type BlanksChallenge = z.infer<typeof BlanksChallenge>
export type NumericChallenge = z.infer<typeof NumericChallenge>
export type TextContractChallenge = z.infer<typeof TextContractChallenge>
export type MachineChallenge = z.infer<typeof MachineChallenge>
export type TuneChallenge = z.infer<typeof TuneChallenge>
export type SpotChallenge = z.infer<typeof SpotChallenge>
export type CustomChallenge = z.infer<typeof CustomChallenge>

/**
 * A lesson's stage 1.
 *
 * Three or four steps. Two is a demo and five is a lesson inside a lesson.
 */
export const ChallengeSet = z.object({
  /** One sentence naming what the learner will be able to do afterwards. */
  goal: z.string().min(1).max(160),
  /**
   * Whether a learner can work these out from what is on the screen.
   *
   * Set it when the challenges carry their own context and discovering the
   * idea is the point: tune a slider until the number moves, repair a payload
   * against rules the challenge states, drive a machine whose transitions are
   * drawn in front of you. Reading then stays optional and the lesson opens on
   * the challenges.
   *
   * Leave it off, which is the default, when a challenge assumes something
   * only the prose says. Sorting failures into "you will hit this here" and
   * "described, never exercised" is not a puzzle, it is a comprehension check,
   * and putting it before the text it checks is a quiz the learner cannot
   * pass. Reading comes first for those.
   *
   * The default is deliberate: a challenge that quietly depends on the prose
   * is the common mistake, and the cost of reading first when you did not need
   * to is smaller than the cost of being asked about something you were never
   * told.
   */
  readingOptional: z.boolean().default(false),
  steps: z.array(Challenge).min(3).max(4),
})
export type ChallengeSet = z.infer<typeof ChallengeSet>

/**
 * The compiled form, which allows a single step.
 *
 * A lesson still on the superseded one-widget `interactive:` spec is lowered
 * into a sequence of one, so the three lessons already authored keep rendering
 * while the catalogue is converted.
 */
export const CompiledChallengeSet = z.object({
  goal: z.string().min(1).max(160),
  readingOptional: z.boolean().default(false),
  steps: z.array(Challenge).min(1).max(4),
})
export type CompiledChallengeSet = z.infer<typeof CompiledChallengeSet>

export const CHALLENGE_KINDS = [
  'choice',
  'order',
  'assign',
  'blanks',
  'numeric',
  'text-contract',
  'machine',
  'tune',
  'spot',
  'custom',
] as const
export type ChallengeKind = (typeof CHALLENGE_KINDS)[number]
