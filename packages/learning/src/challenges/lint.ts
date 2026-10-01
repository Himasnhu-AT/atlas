import {
  type Challenge,
  type ChallengeSet,
  machineIsWinnable,
  checkChallenge,
  checkTextContract,
} from '@atlas/core'

/**
 * The checks a challenge schema cannot express.
 *
 * Zod validates shape. This validates sense, and it is the reason four agents
 * can author several hundred challenges without shipping walls. Without it the
 * predictable failures are a multiple choice with no correct option, an
 * ordering whose solution is not a permutation of its own items, a machine
 * whose goal cannot be reached, and a text buffer that is already correct when
 * the learner arrives.
 *
 * It is the direct analogue of the exercise gate: the reference must pass its
 * own test and the scaffold must fail it, proven by running both.
 */
export function lintChallengeSet(set: ChallengeSet | { goal: string; steps: Challenge[] }): string[] {
  const problems: string[] = []
  const seen = new Set<string>()

  for (const step of set.steps) {
    const at = `challenge "${step.id}"`
    if (seen.has(step.id)) problems.push(`${at} is declared twice`)
    seen.add(step.id)

    for (const [index, hint] of step.hints.entries()) {
      if (hint.trim() === step.prompt.trim()) {
        problems.push(`${at} hint ${index + 1} just repeats the prompt`)
      }
    }

    problems.push(...lintOne(step, at))
  }

  return problems
}

function lintOne(step: Challenge, at: string): string[] {
  const problems: string[] = []

  switch (step.kind) {
    case 'choice': {
      const correct = step.options.filter((option) => option.correct)
      if (correct.length === 0) problems.push(`${at} has no correct option`)
      if (!step.multiple && correct.length > 1) {
        problems.push(`${at} is single choice and marks ${correct.length} options correct`)
      }
      const ids = step.options.map((option) => option.id)
      if (new Set(ids).size !== ids.length) problems.push(`${at} has two options with the same id`)
      break
    }

    case 'order': {
      const items = step.items.map((item) => item.id).sort()
      const solution = [...step.solution].sort()
      if (items.join('|') !== solution.join('|')) {
        problems.push(`${at} solution is not a permutation of its items`)
      }
      for (const id of Object.keys(step.because)) {
        if (!items.includes(id)) problems.push(`${at} explains "${id}", which is not one of its items`)
      }
      break
    }

    case 'assign': {
      const buckets = new Set(step.buckets.map((bucket) => bucket.id))
      for (const item of step.items) {
        if (!buckets.has(item.bucket)) {
          problems.push(`${at} puts "${item.id}" in "${item.bucket}", which is not one of its buckets`)
        }
      }
      // A bucket nothing belongs in is a decoy the learner can never be right
      // about, which reads as a bug rather than as a distractor.
      for (const bucket of step.buckets) {
        if (!step.items.some((item) => item.bucket === bucket.id)) {
          problems.push(`${at} bucket "${bucket.id}" has nothing that belongs in it`)
        }
      }
      break
    }

    case 'blanks': {
      for (const blank of step.blanks) {
        const marker = `{{${blank.n}}}`
        const occurrences = step.template.split(marker).length - 1
        if (occurrences === 0) problems.push(`${at} declares blank ${blank.n}, which the template never uses`)
        if (occurrences > 1) problems.push(`${at} uses ${marker} ${occurrences} times`)
        if (blank.as === 'select') {
          if (blank.options.length < 2) problems.push(`${at} blank ${blank.n} is a select with fewer than two options`)
          const offered = blank.options.map((option) => option.trim().toLowerCase())
          const accepted = blank.accept.map((option) => option.trim().toLowerCase())
          if (!accepted.some((answer) => offered.includes(answer))) {
            problems.push(`${at} blank ${blank.n} offers no option it would accept`)
          }
        }
      }
      const declared = step.blanks.map((blank) => blank.n)
      if (new Set(declared).size !== declared.length) problems.push(`${at} declares a blank number twice`)
      break
    }

    case 'text-contract': {
      // The two halves of the bargain. `initial` already satisfying every rule
      // is a challenge that is solved before the learner reads it, and a
      // `solution` that fails one is a wall.
      if (checkTextContract(step, step.initial).passed) {
        problems.push(`${at} starts already satisfying every rule, so there is nothing to do`)
      }
      const solved = checkTextContract(step, step.solution)
      if (!solved.passed) {
        problems.push(`${at} solution does not pass its own rules: ${solved.message}`)
      }

      // A path assertion reads the parsed document, so something has to have
      // parsed it first. Catching this here means the runtime never has to.
      let parsedYet = false
      for (const [index, rule] of step.rules.entries()) {
        if (rule.check.op === 'parses') {
          parsedYet = true
          continue
        }
        if ('path' in rule.check && rule.check.path !== undefined && !parsedYet) {
          problems.push(`${at} rule ${index + 1} reads a path before any rule has parsed the text`)
        }
      }

      for (const [index, rule] of step.rules.entries()) {
        if (rule.check.op !== 'matches' && rule.check.op !== 'notMatches') continue
        try {
          new RegExp(rule.check.pattern, rule.check.flags)
        } catch (error) {
          problems.push(`${at} rule ${index + 1} pattern will not compile: ${(error as Error).message}`)
          continue
        }
        // Nested quantifiers are how an authored pattern freezes a tab.
        if (/(\([^)]*[+*][^)]*\)[+*])/.test(rule.check.pattern)) {
          problems.push(`${at} rule ${index + 1} nests quantifiers, which can backtrack a browser to a halt`)
        }
      }
      break
    }

    case 'machine': {
      const states = new Set(Object.keys(step.states))
      if (!states.has(step.initial)) problems.push(`${at} starts in "${step.initial}", which is not a state`)
      for (const transition of step.transitions) {
        if (!states.has(transition.from)) problems.push(`${at} has a transition from unknown state "${transition.from}"`)
        if (!states.has(transition.to)) problems.push(`${at} has a transition to unknown state "${transition.to}"`)
      }
      if (step.win.state && !states.has(step.win.state)) {
        problems.push(`${at} wins on "${step.win.state}", which is not a state`)
      }
      if (!machineIsWinnable(step)) {
        problems.push(
          `${at} cannot be finished: no run of at most ${step.win.maxSteps} steps reaches the goal`,
        )
      }
      break
    }

    case 'tune': {
      // Outputs may name inputs and outputs already declared. Anything else is
      // either a typo or a cycle, and a cycle evaluates to zero in silence.
      const known = new Set(step.inputs.map((input) => input.id))
      for (const output of step.outputs) {
        for (const term of output.terms) {
          for (const name of term.of) {
            if (!known.has(name)) {
              problems.push(`${at} output "${output.id}" uses "${name}" before anything defines it`)
            }
          }
        }
        known.add(output.id)
      }
      for (const input of step.inputs) {
        if (input.min >= input.max) problems.push(`${at} input "${input.id}" has an empty range`)
        if (input.initial < input.min || input.initial > input.max) {
          problems.push(`${at} input "${input.id}" starts outside its own range`)
        }
      }
      if (!step.outputs.some((output) => output.target)) {
        problems.push(`${at} has no output with a target, so it cannot be passed`)
      }
      // Same bargain as text-contract: it must not open already solved.
      const start = Object.fromEntries(step.inputs.map((input) => [input.id, input.initial]))
      if (checkChallenge(step, start).passed) {
        problems.push(`${at} starts inside its own target, so there is nothing to tune`)
      }
      break
    }

    case 'spot': {
      const lines = step.source.split('\n').length
      for (const target of step.targets) {
        if (target >= lines) problems.push(`${at} marks line ${target}, and the source has ${lines}`)
      }
      for (const index of Object.keys(step.decoys)) {
        if (step.targets.includes(Number(index))) {
          problems.push(`${at} calls line ${index} both a target and a decoy`)
        }
      }
      break
    }

    case 'numeric': {
      if (step.tolerance < 0) problems.push(`${at} has a negative tolerance`)
      break
    }

    case 'custom':
      // Props are checked against the component's own schema by the caller,
      // which is the only thing that knows the registry.
      break
  }

  return problems
}
