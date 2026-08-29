import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  checkAssign,
  checkBlanks,
  checkChoice,
  checkMachine,
  checkNumeric,
  checkOrder,
  checkSpot,
  checkTextContract,
  checkTune,
  evaluateTune,
  machineIsWinnable,
  machineStart,
  offeredActions,
  stepMachine,
  type MachineChallenge,
  type TextContractChallenge,
  type TuneChallenge,
} from './index'

const base = { hints: ['a'], reveal: 'r' } as const

/* --------------------------------------------------------- text contract */

/**
 * The challenge that replaced `StructuredOutputWorkbench`'s first step. Its
 * verification was 23 lines of hand-written cascade; this is the same cascade
 * as data, and these tests are the ones that prove they mean the same thing.
 */
const isolate: TextContractChallenge = {
  ...base,
  kind: 'text-contract',
  id: 'isolate',
  prompt: 'p',
  lang: 'json',
  initial: 'Sure! ```json\n{"customer_name": "Ana"}\n``` Hope this helps',
  solution: '{"customer_name": "Ana", "quantity": 2}',
  rules: [
    { message: 'prose is still wrapped around it', check: { op: 'notMatches', pattern: 'Sure!|Hope this helps', flags: '' } },
    { message: 'the fence is still there', check: { op: 'notContains', text: '```', caseSensitive: false } },
    { message: 'that does not parse', check: { op: 'parses', as: 'json' } },
    { message: 'quantity must be a whole number', check: { op: 'type', path: 'quantity', is: 'integer' } },
  ],
}

test('the first failing rule is the message, in author order', () => {
  assert.equal(checkTextContract(isolate, isolate.initial).message, 'prose is still wrapped around it')
  assert.equal(checkTextContract(isolate, '```json\n{"a":1}\n```').message, 'the fence is still there')
  assert.equal(checkTextContract(isolate, '{not json').message, 'that does not parse')
  assert.equal(
    checkTextContract(isolate, '{"quantity": "two"}').message,
    'quantity must be a whole number',
  )
})

test('a parse failure carries the parser complaint as detail', () => {
  const verdict = checkTextContract(isolate, '{not json')
  assert.equal(verdict.passed, false)
  assert.ok(verdict.detail && verdict.detail.length > 0)
})

test('the authored solution passes and the authored start does not', () => {
  // This pair is exactly what the content build asserts for every authored
  // text-contract, and it is the same bargain as reference-passes /
  // scaffold-fails on the coding exercises.
  assert.equal(checkTextContract(isolate, isolate.solution).passed, true)
  assert.equal(checkTextContract(isolate, isolate.initial).passed, false)
})

test('a boolean does not satisfy an integer type check', () => {
  const challenge: TextContractChallenge = {
    ...isolate,
    rules: [
      { message: 'parse', check: { op: 'parses', as: 'json' } },
      { message: 'urgent must be a whole number', check: { op: 'type', path: 'urgent', is: 'integer' } },
    ],
  }
  // The JSON analogue of Python's isinstance(True, int) being True, which the
  // lesson this came from calls out by name.
  assert.equal(checkTextContract(challenge, '{"urgent": true}').passed, false)
  assert.equal(checkTextContract(challenge, '{"urgent": 1}').passed, true)
})

test('a missing key fails exists, and a null one does not', () => {
  const challenge: TextContractChallenge = {
    ...isolate,
    rules: [
      { message: 'parse', check: { op: 'parses', as: 'json' } },
      { message: 'order_id may be null but not absent', check: { op: 'exists', path: 'order_id' } },
    ],
  }
  assert.equal(checkTextContract(challenge, '{}').passed, false)
  assert.equal(checkTextContract(challenge, '{"order_id": null}').passed, true)
})

test('oneOf and range read the parsed document', () => {
  const challenge: TextContractChallenge = {
    ...isolate,
    rules: [
      { message: 'parse', check: { op: 'parses', as: 'json' } },
      { message: 'status is outside the contract', check: { op: 'oneOf', path: 'status', values: ['open', 'shipped'] } },
      { message: 'quantity must be at least 1', check: { op: 'range', path: 'quantity', min: 1 } },
    ],
  }
  assert.equal(checkTextContract(challenge, '{"status":"pending","quantity":2}').message, 'status is outside the contract')
  assert.equal(checkTextContract(challenge, '{"status":"open","quantity":0}').message, 'quantity must be at least 1')
  assert.equal(checkTextContract(challenge, '{"status":"open","quantity":1}').passed, true)
})

test('a malformed pattern refuses rather than throwing', () => {
  const challenge: TextContractChallenge = {
    ...isolate,
    rules: [{ message: 'nope', check: { op: 'matches', pattern: '([', flags: '' } }],
  }
  assert.equal(checkTextContract(challenge, 'anything').passed, false)
})

/* ---------------------------------------------------------------- choice */

const choice = {
  ...base,
  kind: 'choice' as const,
  id: 'c',
  prompt: 'p',
  multiple: false,
  options: [
    { id: 'vague', label: 'try again', correct: false, note: 'the model cannot see what was wrong' },
    { id: 'full', label: 'reply plus error', correct: true, note: 'the smallest complete repair request' },
  ],
}

test('a wrong choice is answered with that option own note', () => {
  assert.equal(checkChoice(choice, ['vague']).message, 'the model cannot see what was wrong')
  assert.equal(checkChoice(choice, ['full']).passed, true)
  assert.equal(checkChoice(choice, []).passed, false)
})

/* ----------------------------------------------------------------- order */

const order = {
  ...base,
  kind: 'order' as const,
  id: 'o',
  prompt: 'p',
  items: [
    { id: 'extract', label: 'find it' },
    { id: 'parse', label: 'parse it' },
    { id: 'validate', label: 'validate it' },
  ],
  solution: ['extract', 'parse', 'validate'],
  because: { parse: 'the reply is a string before it is a document' },
}

test('order names the earliest wrong position, not a score', () => {
  assert.equal(checkOrder(order, ['extract', 'parse', 'validate']).passed, true)
  assert.equal(
    checkOrder(order, ['extract', 'validate', 'parse']).message,
    'the reply is a string before it is a document',
  )
  assert.equal(checkOrder(order, ['extract']).passed, false)
})

/* ---------------------------------------------------------------- assign */

test('assign reports the misplaced item, and refuses a partial answer', () => {
  const assign = {
    ...base,
    kind: 'assign' as const,
    id: 'a',
    prompt: 'p',
    buckets: [{ id: 'stack', label: 'stack' }, { id: 'heap', label: 'heap' }],
    items: [
      { id: 'local', label: 'a local int', bucket: 'stack' },
      { id: 'malloc', label: 'a malloc result', bucket: 'heap', because: 'malloc always returns heap memory' },
    ],
  }
  assert.equal(checkAssign(assign, { local: 'stack', malloc: 'heap' }).passed, true)
  assert.equal(checkAssign(assign, { local: 'stack', malloc: 'stack' }).message, 'malloc always returns heap memory')
  assert.equal(checkAssign(assign, { local: 'stack' }).passed, false)
})

/* ---------------------------------------------------------------- blanks */

test('blanks accept any listed answer, trimmed and case folded', () => {
  const blanks = {
    ...base,
    kind: 'blanks' as const,
    id: 'b',
    prompt: 'p',
    lang: 'python',
    template: 'json.{{1}}(reply)',
    blanks: [{ n: 1, as: 'select' as const, options: ['loads', 'dumps'], accept: ['loads'], note: 'you are reading, not writing' }],
  }
  assert.equal(checkBlanks(blanks, { 1: '  LOADS ' }).passed, true)
  assert.equal(checkBlanks(blanks, { 1: 'dumps' }).message, 'you are reading, not writing')
  assert.equal(checkBlanks(blanks, {}).passed, false)
})

/* --------------------------------------------------------------- numeric */

test('numeric honours tolerance and calls out an order of magnitude', () => {
  const numeric = {
    ...base,
    kind: 'numeric' as const,
    id: 'n',
    prompt: 'p',
    answer: 4096,
    tolerance: 64,
    scaleHint: 'that is tokens against characters',
  }
  assert.equal(checkNumeric(numeric, 4100).passed, true)
  assert.equal(checkNumeric(numeric, 4200).passed, false)
  assert.equal(checkNumeric(numeric, 16, ).message, 'that is tokens against characters')
  assert.equal(checkNumeric(numeric, Number.NaN).passed, false)
})

/* ------------------------------------------------------------------ spot */

test('spot explains an innocent line rather than only rejecting it', () => {
  const spot = {
    ...base,
    kind: 'spot' as const,
    id: 's',
    prompt: 'p',
    lang: 'python',
    source: 'a\nb\nc',
    targets: [1],
    requireAll: true,
    decoys: { '0': 'that line only reads' },
  }
  assert.equal(checkSpot(spot, [1]).passed, true)
  assert.equal(checkSpot(spot, [0]).message, 'that line only reads')
  assert.equal(checkSpot(spot, []).passed, false)
})

/* ------------------------------------------------------------------ tune */

const tune: TuneChallenge = {
  ...base,
  kind: 'tune',
  id: 't',
  prompt: 'p',
  inputs: [
    { id: 'turns', label: 'turns', min: 0, max: 20, step: 1, initial: 8 },
    { id: 'perturn', label: 'tokens per turn', min: 10, max: 400, step: 10, initial: 200 },
  ],
  outputs: [
    { id: 'history', label: 'history', terms: [{ coef: 1, of: ['turns', 'perturn'] }] },
    {
      id: 'headroom',
      label: 'headroom',
      terms: [{ coef: 4096, of: [] }, { coef: -1, of: ['history'] }],
      target: { min: 512 },
      note: 'there is no room left for a reply',
    },
  ],
}

test('tune evaluates outputs in order and lets later ones use earlier ones', () => {
  const values = evaluateTune(tune, { turns: 8, perturn: 200 })
  assert.equal(values.history, 1600)
  assert.equal(values.headroom, 2496)
})

test('tune fails outside the target window and passes inside it', () => {
  assert.equal(checkTune(tune, { turns: 8, perturn: 200 }).passed, true)
  assert.equal(checkTune(tune, { turns: 20, perturn: 400 }).message, 'there is no room left for a reply')
})

/* --------------------------------------------------------------- machine */

const react: MachineChallenge = {
  ...base,
  kind: 'machine',
  id: 'm',
  prompt: 'p',
  initial: 'thinking',
  vars: { retries: 0 },
  states: {
    thinking: { label: 'Thinking', terminal: false, error: false },
    calling: { label: 'Calling a tool', terminal: false, error: false },
    failed: { label: 'Tool errored', terminal: false, error: true },
    done: { label: 'Answered', terminal: true, error: false },
  },
  transitions: [
    { from: 'thinking', on: 'call', to: 'calling', when: [], effects: [] },
    { from: 'calling', on: 'error', to: 'failed', when: [], effects: [] },
    { from: 'calling', on: 'result', to: 'done', when: [], effects: [] },
    {
      from: 'failed',
      on: 'retry',
      to: 'calling',
      when: [{ var: 'retries', cmp: 'lt', value: 2 }],
      effects: [{ var: 'retries', op: 'inc', value: 1 }],
      note: 'a retry costs one from the budget',
    },
  ],
  mode: 'drive',
  win: { state: 'done', maxSteps: 8, requires: [{ var: 'retries', cmp: 'lte', value: 2 }] },
}

test('a guard that fails is not offered as an action', () => {
  let state = machineStart(react)
  state = stepMachine(react, state, 'call')
  state = stepMachine(react, state, 'error')
  assert.deepEqual(offeredActions(react, state).map((t) => t.on), ['retry'])

  // Spend the budget, and the retry stops being on the table.
  state = stepMachine(react, state, 'retry')
  state = stepMachine(react, state, 'error')
  state = stepMachine(react, state, 'retry')
  state = stepMachine(react, state, 'error')
  assert.deepEqual(offeredActions(react, state).map((t) => t.on), [])
})

test('an unavailable action leaves the machine where it was', () => {
  const start = machineStart(react)
  assert.deepEqual(stepMachine(react, start, 'retry'), start)
})

test('the goal needs the state and every budget together', () => {
  let state = machineStart(react)
  state = stepMachine(react, state, 'call')
  assert.equal(checkMachine(react, state).passed, false)
  state = stepMachine(react, state, 'result')
  assert.equal(checkMachine(react, state).passed, true)
})

test('an unreachable goal is caught before it reaches a learner', () => {
  assert.equal(machineIsWinnable(react), true)

  const walled: MachineChallenge = {
    ...react,
    // Nothing leads out of `failed` once the retries are spent, so a machine
    // that demands `done` after three failures cannot be finished.
    win: { state: 'done', maxSteps: 8, requires: [{ var: 'retries', cmp: 'gte', value: 3 }] },
  }
  assert.equal(machineIsWinnable(walled), false)
})

test('winnability terminates on a machine that can loop forever', () => {
  const looping: MachineChallenge = {
    ...react,
    transitions: [
      { from: 'thinking', on: 'again', to: 'thinking', when: [], effects: [] },
    ],
    win: { state: 'done', maxSteps: 30, requires: [] },
  }
  assert.equal(machineIsWinnable(looping), false)
})
