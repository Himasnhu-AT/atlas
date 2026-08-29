import assert from 'node:assert/strict'
import { test } from 'node:test'

import type { Challenge } from '@atlas/core'

import { lintChallengeSet } from './lint'

/**
 * The gate that stands between four agents and several hundred authored
 * challenges.
 *
 * Every case here is a challenge that would reach a learner as either a wall
 * or a freebie, and neither is visible by reading the YAML. A machine whose
 * goal stops being reachable once a guard spends its budget looks completely
 * reasonable on the page.
 */

const base = { hints: ['a hint'], reveal: 'the point' }

/** Lint one step, and return the problems that name it. */
function lintStep(step: Challenge): string[] {
  return lintChallengeSet({ goal: 'g', steps: [step] })
}

const contract: Challenge = {
  ...base,
  kind: 'text-contract',
  id: 'fix-it',
  prompt: 'repair the payload',
  lang: 'json',
  initial: '{"quantity": "two"}',
  solution: '{"quantity": 2}',
  rules: [
    { message: 'that does not parse', check: { op: 'parses', as: 'json' } },
    { message: 'quantity must be whole', check: { op: 'type', path: 'quantity', is: 'integer' } },
  ],
}

test('a well formed set produces no problems', () => {
  assert.deepEqual(lintStep(contract), [])
})

test('a text-contract that opens already solved is rejected', () => {
  const problems = lintStep({ ...contract, initial: contract.solution })
  assert.ok(problems.some((p) => p.includes('nothing to do')), problems.join('; '))
})

test('a text-contract whose solution fails its own rules is rejected', () => {
  const problems = lintStep({ ...contract, solution: '{"quantity": "still a word"}' })
  assert.ok(problems.some((p) => p.includes('does not pass its own rules')), problems.join('; '))
})

test('a rule reading a path before anything parses is rejected', () => {
  const problems = lintStep({ ...contract, rules: [contract.rules[1]!] })
  assert.ok(problems.some((p) => p.includes('before any rule has parsed')), problems.join('; '))
})

test('a pattern that nests quantifiers is rejected', () => {
  // Not style. An authored pattern that backtracks freezes the learner's tab,
  // and it is the one thing in the rule vocabulary that can.
  const problems = lintStep({
    ...contract,
    rules: [{ message: 'no', check: { op: 'matches', pattern: '(a+)+b', flags: '' } }],
  })
  assert.ok(problems.some((p) => p.includes('nests quantifiers')), problems.join('; '))
})

test('a choice needs exactly one correct option when it is single choice', () => {
  const choice = {
    ...base,
    kind: 'choice' as const,
    id: 'pick',
    prompt: 'p',
    multiple: false,
    options: [
      { id: 'a', label: 'A', correct: false, note: 'why not' },
      { id: 'b', label: 'B', correct: false, note: 'why not' },
    ],
  }
  assert.ok(lintStep(choice).some((p) => p.includes('no correct option')))

  const both = {
    ...choice,
    options: choice.options.map((option) => ({ ...option, correct: true })),
  }
  assert.ok(lintStep(both).some((p) => p.includes('marks 2 options correct')))
})

test('an ordering solution must be a permutation of its own items', () => {
  const order = {
    ...base,
    kind: 'order' as const,
    id: 'seq',
    prompt: 'p',
    items: [
      { id: 'one', label: 'one' },
      { id: 'two', label: 'two' },
      { id: 'three', label: 'three' },
    ],
    solution: ['one', 'two', 'nonsense'],
    because: {},
  }
  assert.ok(lintStep(order).some((p) => p.includes('not a permutation')))
})

test('an assign bucket nothing belongs in is rejected', () => {
  const assign = {
    ...base,
    kind: 'assign' as const,
    id: 'sort',
    prompt: 'p',
    buckets: [
      { id: 'stack', label: 'stack' },
      { id: 'heap', label: 'heap' },
      { id: 'static', label: 'static' },
    ],
    items: [
      { id: 'a', label: 'a', bucket: 'stack' },
      { id: 'b', label: 'b', bucket: 'heap' },
      { id: 'c', label: 'c', bucket: 'stack' },
    ],
  }
  // A bucket that is never correct is a distractor the learner cannot resolve,
  // and it reads as a bug rather than as a choice.
  assert.ok(lintStep(assign).some((p) => p.includes('nothing that belongs in it')))
})

test('a blanks select must offer an answer it would accept', () => {
  const blanks = {
    ...base,
    kind: 'blanks' as const,
    id: 'fill',
    prompt: 'p',
    lang: 'python',
    template: 'json.{{1}}(reply)',
    blanks: [{ n: 1, as: 'select' as const, options: ['dumps', 'dump'], accept: ['loads'] }],
  }
  assert.ok(lintStep(blanks).some((p) => p.includes('offers no option it would accept')))
})

test('a blank the template never uses is rejected', () => {
  const blanks = {
    ...base,
    kind: 'blanks' as const,
    id: 'fill',
    prompt: 'p',
    lang: 'python',
    template: 'json.{{1}}(reply)',
    blanks: [
      { n: 1, as: 'type' as const, options: [], accept: ['loads'] },
      { n: 2, as: 'type' as const, options: [], accept: ['x'] },
    ],
  }
  assert.ok(lintStep(blanks).some((p) => p.includes('which the template never uses')))
})

test('a machine whose goal cannot be reached is rejected', () => {
  const machine = {
    ...base,
    kind: 'machine' as const,
    id: 'loop',
    prompt: 'p',
    initial: 'start',
    vars: { retries: 0 },
    states: {
      start: { label: 'Start', terminal: false, error: false },
      done: { label: 'Done', terminal: true, error: false },
    },
    transitions: [
      {
        from: 'start',
        on: 'go',
        to: 'done',
        when: [],
        effects: [{ var: 'retries', op: 'inc' as const, value: 1 }],
      },
    ],
    mode: 'drive' as const,
    // Reaching `done` always costs exactly one retry, so demanding zero is a
    // goal no run can satisfy. This is the failure that is invisible on the
    // page and total for the learner.
    win: { state: 'done', maxSteps: 5, requires: [{ var: 'retries', cmp: 'eq' as const, value: 0 }] },
  }
  assert.ok(lintStep(machine).some((p) => p.includes('cannot be finished')))

  const winnable = { ...machine, win: { ...machine.win, requires: [] } }
  assert.deepEqual(lintStep(winnable), [])
})

test('a machine naming a state that does not exist is rejected', () => {
  const machine = {
    ...base,
    kind: 'machine' as const,
    id: 'typo',
    prompt: 'p',
    initial: 'start',
    vars: {},
    states: { start: { label: 'Start', terminal: false, error: false } },
    transitions: [{ from: 'start', on: 'go', to: 'finish', when: [], effects: [] }],
    mode: 'drive' as const,
    win: { state: 'finish', maxSteps: 5, requires: [] },
  }
  const problems = lintStep(machine)
  assert.ok(problems.some((p) => p.includes('unknown state "finish"')), problems.join('; '))
})

test('a tune that opens inside its own target is rejected', () => {
  const tune = {
    ...base,
    kind: 'tune' as const,
    id: 'dial',
    prompt: 'p',
    inputs: [{ id: 'x', label: 'x', min: 0, max: 10, step: 1, initial: 5 }],
    outputs: [
      { id: 'y', label: 'y', terms: [{ coef: 1, of: ['x'] }], target: { min: 0, max: 10 } },
    ],
  }
  assert.ok(lintStep(tune).some((p) => p.includes('starts inside its own target')))
})

test('a tune output naming something undefined is rejected', () => {
  const tune = {
    ...base,
    kind: 'tune' as const,
    id: 'dial',
    prompt: 'p',
    inputs: [{ id: 'x', label: 'x', min: 0, max: 10, step: 1, initial: 1 }],
    outputs: [
      { id: 'y', label: 'y', terms: [{ coef: 1, of: ['z'] }], target: { min: 100 } },
    ],
  }
  // Silently evaluates to zero otherwise, so the learner drags a slider that
  // changes nothing.
  assert.ok(lintStep(tune).some((p) => p.includes('before anything defines it')))
})

test('a spot line that is both target and decoy is rejected', () => {
  const spot = {
    ...base,
    kind: 'spot' as const,
    id: 'find',
    prompt: 'p',
    lang: 'python',
    source: 'a\nb\nc',
    targets: [1],
    requireAll: true,
    decoys: { '1': 'contradicts itself' },
  }
  assert.ok(lintStep(spot).some((p) => p.includes('both a target and a decoy')))
})

test('a duplicate step id is rejected', () => {
  const problems = lintChallengeSet({ goal: 'g', steps: [contract, contract] })
  assert.ok(problems.some((p) => p.includes('declared twice')))
})

test('a hint that only repeats the prompt is rejected', () => {
  const problems = lintStep({ ...contract, hints: ['repair the payload'] })
  assert.ok(problems.some((p) => p.includes('repeats the prompt')))
})
