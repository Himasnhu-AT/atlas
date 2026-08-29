import type {
  AssignChallenge,
  BlanksChallenge,
  Challenge,
  ChoiceChallenge,
  MachineChallenge,
  NumericChallenge,
  OrderChallenge,
  SpotChallenge,
  TextContractChallenge,
  TuneChallenge,
} from './kinds'
import type { Assertion } from './rules'

/**
 * Checking a challenge, as pure functions.
 *
 * These run in three places and must agree in all of them: in the browser when
 * a learner presses Check, in the desktop webview, and in the content build,
 * which uses them to prove that every authored challenge is actually solvable
 * and not already solved. That last one is the whole reason they live here
 * rather than inside a React component. It is the same idea as the existing
 * exercise gate, where the reference must pass its own test and the scaffold
 * must fail it.
 */

export interface Verdict {
  passed: boolean
  /** What to tell the learner. Absent on a pass. */
  message?: string
  /** Extra specifics, such as a parser's own complaint. */
  detail?: string
}

const PASS: Verdict = { passed: true }

/* ------------------------------------------------------------------ paths */

/** Walk a dotted path. Returns `undefined` for anything absent. */
export function resolvePath(value: unknown, path: string): unknown {
  let current = value
  for (const key of path.split('.')) {
    if (current === null || typeof current !== 'object') return undefined
    current = (current as Record<string, unknown>)[key]
  }
  return current
}

function pathExists(value: unknown, path: string): boolean {
  const keys = path.split('.')
  let current = value
  for (let index = 0; index < keys.length; index += 1) {
    if (current === null || typeof current !== 'object') return false
    if (!Object.prototype.hasOwnProperty.call(current, keys[index]!)) return false
    current = (current as Record<string, unknown>)[keys[index]!]
  }
  return true
}

function typeOf(value: unknown): string {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  // `typeof true === 'boolean'` already, but Python's isinstance(True, int)
  // trap has a JSON analogue: authors reach for `number` and mean not-boolean.
  return typeof value
}

function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

/* --------------------------------------------------------- text contract */

function tryParse(text: string, as: 'json' | 'integer' | 'number') {
  const trimmed = text.trim()
  if (as === 'json') {
    try {
      return { ok: true as const, value: JSON.parse(trimmed) as unknown }
    } catch (error) {
      return { ok: false as const, error: (error as Error).message }
    }
  }
  const parsed = Number(trimmed)
  if (trimmed.length === 0 || Number.isNaN(parsed)) {
    return { ok: false as const, error: `${JSON.stringify(trimmed)} is not a number` }
  }
  if (as === 'integer' && !Number.isInteger(parsed)) {
    return { ok: false as const, error: `${parsed} is not a whole number` }
  }
  return { ok: true as const, value: parsed }
}

function textOf(value: unknown): string {
  return typeof value === 'string' ? value : value === undefined ? '' : JSON.stringify(value)
}

function satisfies(assertion: Assertion, subject: unknown, raw: string): boolean {
  switch (assertion.op) {
    case 'parses':
      return true // handled before this point
    case 'exists':
      return subject !== undefined
    case 'absent':
      return subject === undefined
    case 'type': {
      if (assertion.is === 'integer') return typeof subject === 'number' && Number.isInteger(subject)
      return typeOf(subject) === assertion.is
    }
    case 'equals':
      return sameValue(subject, assertion.value)
    case 'oneOf':
      return assertion.values.some((candidate) => sameValue(subject, candidate))
    case 'range': {
      if (typeof subject !== 'number') return false
      if (assertion.min !== undefined && subject < assertion.min) return false
      if (assertion.max !== undefined && subject > assertion.max) return false
      return true
    }
    case 'length': {
      const target = assertion.path === undefined ? raw : subject
      const size =
        typeof target === 'string' || Array.isArray(target)
          ? target.length
          : target !== null && typeof target === 'object'
            ? Object.keys(target).length
            : undefined
      if (size === undefined) return false
      if (assertion.min !== undefined && size < assertion.min) return false
      if (assertion.max !== undefined && size > assertion.max) return false
      return true
    }
    case 'contains':
    case 'notContains': {
      const haystack = assertion.path === undefined ? raw : textOf(subject)
      const found = assertion.caseSensitive
        ? haystack.includes(assertion.text)
        : haystack.toLowerCase().includes(assertion.text.toLowerCase())
      return assertion.op === 'contains' ? found : !found
    }
    case 'matches':
    case 'notMatches': {
      const haystack = assertion.path === undefined ? raw : textOf(subject)
      let matched: boolean
      try {
        matched = new RegExp(assertion.pattern, assertion.flags).test(haystack)
      } catch {
        // A pattern the build should have rejected. Refusing to pass is safer
        // than throwing inside a learner's click handler.
        return false
      }
      return assertion.op === 'matches' ? matched : !matched
    }
  }
}

export function checkTextContract(challenge: TextContractChallenge, buffer: string): Verdict {
  let parsed: unknown
  let haveParsed = false

  for (const rule of challenge.rules) {
    const assertion = rule.check

    if (assertion.op === 'parses') {
      const result = tryParse(buffer, assertion.as)
      if (!result.ok) return { passed: false, message: rule.message, detail: result.error }
      parsed = result.value
      haveParsed = true
      continue
    }

    const usesPath = 'path' in assertion && assertion.path !== undefined
    if (usesPath && !haveParsed) {
      // The build rejects a path assertion with no preceding `parses`, so this
      // is unreachable from validated content and exists so an unvalidated
      // caller fails loudly rather than silently passing.
      return { passed: false, message: rule.message, detail: 'nothing has been parsed yet' }
    }

    let subject: unknown = buffer
    if (usesPath) {
      const path = (assertion as { path: string }).path
      subject = assertion.op === 'exists' || assertion.op === 'absent'
        ? pathExists(parsed, path)
          ? resolvePath(parsed, path)
          : undefined
        : resolvePath(parsed, path)
    }

    if (!satisfies(assertion, subject, buffer)) {
      return { passed: false, message: rule.message }
    }
  }

  return PASS
}

/* ----------------------------------------------------------------- choice */

export function checkChoice(challenge: ChoiceChallenge, selected: string[]): Verdict {
  const correct = challenge.options.filter((option) => option.correct).map((option) => option.id)
  const chosen = [...new Set(selected)].sort()
  const wanted = [...correct].sort()

  if (chosen.length === 0) return { passed: false, message: 'Pick one to see what it costs.' }
  if (chosen.join('|') === wanted.join('|')) return PASS

  // The note on whatever they picked is more useful than "wrong": it says why
  // that specific option fails, which is the thing they were reasoning about.
  const first = challenge.options.find((option) => option.id === chosen[0])
  return { passed: false, message: first?.note ?? 'Not that one.' }
}

/* ------------------------------------------------------------------ order */

export function checkOrder(challenge: OrderChallenge, given: string[]): Verdict {
  if (given.length !== challenge.solution.length) {
    return { passed: false, message: 'Every step has to be placed.' }
  }
  const firstWrong = challenge.solution.findIndex((id, index) => given[index] !== id)
  if (firstWrong === -1) return PASS

  const expected = challenge.solution[firstWrong]!
  return {
    passed: false,
    // Names the earliest position that is wrong rather than how many are, so
    // the learner has one thing to reconsider instead of a score.
    message:
      challenge.because[expected] ??
      `Position ${firstWrong + 1} is not right yet. Everything before it is.`,
  }
}

/* ----------------------------------------------------------------- assign */

export function checkAssign(
  challenge: AssignChallenge,
  placed: Record<string, string>,
): Verdict {
  const unplaced = challenge.items.filter((item) => !placed[item.id])
  if (unplaced.length > 0) return { passed: false, message: 'Some of these are still unsorted.' }

  const wrong = challenge.items.find((item) => placed[item.id] !== item.bucket)
  if (!wrong) return PASS

  return {
    passed: false,
    message: wrong.because ?? `${wrong.label} is not in the right place.`,
  }
}

/* ----------------------------------------------------------------- blanks */

export function checkBlanks(challenge: BlanksChallenge, given: Record<number, string>): Verdict {
  for (const blank of challenge.blanks) {
    const answer = (given[blank.n] ?? '').trim()
    if (answer.length === 0) return { passed: false, message: 'One of the blanks is still empty.' }
    const ok = blank.accept.some((candidate) => candidate.trim().toLowerCase() === answer.toLowerCase())
    if (!ok) {
      return { passed: false, message: blank.note ?? `Blank ${blank.n} is not right yet.` }
    }
  }
  return PASS
}

/* ---------------------------------------------------------------- numeric */

export function checkNumeric(challenge: NumericChallenge, given: number): Verdict {
  if (!Number.isFinite(given)) return { passed: false, message: 'That is not a number.' }
  if (Math.abs(given - challenge.answer) <= challenge.tolerance) return PASS

  // Out by an order of magnitude is a different mistake from out by a little:
  // they used the wrong quantity, not the wrong arithmetic.
  const ratio = challenge.answer === 0 ? Infinity : Math.abs(given / challenge.answer)
  if (challenge.scaleHint && (ratio >= 10 || ratio <= 0.1)) {
    return { passed: false, message: challenge.scaleHint }
  }
  return { passed: false, message: 'Not yet. Check which quantity each term is measured in.' }
}

/* ------------------------------------------------------------------- spot */

export function checkSpot(challenge: SpotChallenge, clicked: number[]): Verdict {
  const chosen = new Set(clicked)
  if (chosen.size === 0) return { passed: false, message: 'Click the line that causes it.' }

  const stray = [...chosen].find((line) => !challenge.targets.includes(line))
  if (stray !== undefined) {
    return { passed: false, message: challenge.decoys[String(stray)] ?? 'That line is fine.' }
  }
  if (challenge.requireAll && chosen.size < challenge.targets.length) {
    return { passed: false, message: 'There is more than one.' }
  }
  return PASS
}

/* ------------------------------------------------------------------- tune */

export type TuneReadings = Record<string, number>

/** Evaluate every output from the current input values, in declaration order. */
export function evaluateTune(challenge: TuneChallenge, inputs: TuneReadings): TuneReadings {
  const values: TuneReadings = { ...inputs }
  for (const output of challenge.outputs) {
    values[output.id] = output.terms.reduce((total, term) => {
      const product = term.of.reduce((acc, name) => acc * (values[name] ?? 0), 1)
      return total + term.coef * product
    }, 0)
  }
  return values
}

export function checkTune(challenge: TuneChallenge, inputs: TuneReadings): Verdict {
  const values = evaluateTune(challenge, inputs)
  for (const output of challenge.outputs) {
    if (!output.target) continue
    const value = values[output.id] ?? 0
    if (output.target.min !== undefined && value < output.target.min) {
      return { passed: false, message: output.note ?? `${output.label} is still too low.` }
    }
    if (output.target.max !== undefined && value > output.target.max) {
      return { passed: false, message: output.note ?? `${output.label} is still too high.` }
    }
  }
  return PASS
}

/* ---------------------------------------------------------------- machine */

export interface MachineState {
  at: string
  vars: Record<string, number>
  steps: number
}

export function machineStart(challenge: MachineChallenge): MachineState {
  return { at: challenge.initial, vars: { ...challenge.vars }, steps: 0 }
}

function holds(test: { var: string; cmp: string; value: number }, vars: Record<string, number>) {
  const value = vars[test.var] ?? 0
  switch (test.cmp) {
    case 'lt':
      return value < test.value
    case 'lte':
      return value <= test.value
    case 'eq':
      return value === test.value
    case 'gte':
      return value >= test.value
    case 'gt':
      return value > test.value
    default:
      return false
  }
}

/** The actions available right now. A guard that fails is not offered at all. */
export function offeredActions(challenge: MachineChallenge, state: MachineState) {
  return challenge.transitions.filter(
    (transition) =>
      transition.from === state.at && transition.when.every((test) => holds(test, state.vars)),
  )
}

export function stepMachine(
  challenge: MachineChallenge,
  state: MachineState,
  on: string,
): MachineState {
  const transition = offeredActions(challenge, state).find((candidate) => candidate.on === on)
  if (!transition) return state

  const vars = { ...state.vars }
  for (const effect of transition.effects) {
    const current = vars[effect.var] ?? 0
    vars[effect.var] =
      effect.op === 'set' ? effect.value : effect.op === 'inc' ? current + effect.value : current - effect.value
  }
  return { at: transition.to, vars, steps: state.steps + 1 }
}

export function checkMachine(challenge: MachineChallenge, state: MachineState): Verdict {
  const atGoal = challenge.win.state === undefined || state.at === challenge.win.state
  const held = challenge.win.requires.every((test) => holds(test, state.vars))

  if (atGoal && held) return PASS

  if (state.steps >= challenge.win.maxSteps) {
    return { passed: false, message: 'That took more steps than the budget allows. Start again.' }
  }
  if (atGoal && !held) {
    const broken = challenge.win.requires.find((test) => !holds(test, state.vars))
    return { passed: false, message: `You arrived, but ${broken?.var} is outside its budget.` }
  }
  return { passed: false, message: 'Not there yet.' }
}

/**
 * Is the goal reachable at all, within the step budget?
 *
 * A breadth-first walk of the transition graph, used by the content build to
 * refuse a machine whose goal cannot be reached. It is the direct analogue of
 * the reference solution having to pass its own test: an unsolvable challenge
 * is a wall, and four agents authoring hundreds of them will build walls.
 */
export function machineIsWinnable(challenge: MachineChallenge): boolean {
  const seen = new Set<string>()
  let frontier: MachineState[] = [machineStart(challenge)]

  for (let depth = 0; depth <= challenge.win.maxSteps; depth += 1) {
    const next: MachineState[] = []
    for (const state of frontier) {
      if (checkMachine(challenge, state).passed) return true
      const key = `${state.at}|${JSON.stringify(state.vars)}`
      if (seen.has(key)) continue
      seen.add(key)
      for (const action of offeredActions(challenge, state)) {
        next.push(stepMachine(challenge, state, action.on))
      }
    }
    if (next.length === 0) return false
    frontier = next
  }
  return false
}

/* ------------------------------------------------------------------ front */

/**
 * Check any kit challenge.
 *
 * `custom` is absent on purpose: a bespoke component owns its own simulation
 * and reports its own verdict, which is the reason it is bespoke.
 */
export function checkChallenge(challenge: Challenge, answer: unknown): Verdict {
  switch (challenge.kind) {
    case 'choice':
      return checkChoice(challenge, Array.isArray(answer) ? (answer as string[]) : [])
    case 'order':
      return checkOrder(challenge, Array.isArray(answer) ? (answer as string[]) : [])
    case 'assign':
      return checkAssign(challenge, (answer ?? {}) as Record<string, string>)
    case 'blanks':
      return checkBlanks(challenge, (answer ?? {}) as Record<number, string>)
    case 'numeric':
      return checkNumeric(challenge, typeof answer === 'number' ? answer : Number(answer))
    case 'text-contract':
      return checkTextContract(challenge, typeof answer === 'string' ? answer : '')
    case 'spot':
      return checkSpot(challenge, Array.isArray(answer) ? (answer as number[]) : [])
    case 'tune':
      return checkTune(challenge, (answer ?? {}) as TuneReadings)
    case 'machine':
      return checkMachine(challenge, (answer ?? machineStart(challenge)) as MachineState)
    case 'custom':
      return { passed: false, message: 'This one reports its own result.' }
  }
}
