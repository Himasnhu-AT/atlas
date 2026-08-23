import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { SEALS, SEALS_BY_ID, type SealEvidence, emptyEvidence, newlyEarnedSeals } from './seals'

const evidence = (over: Partial<SealEvidence> = {}): SealEvidence => ({
  ...emptyEvidence(),
  ...over,
})

describe('the seal table', () => {
  it('has unique ids', () => {
    const ids = SEALS.map((s) => s.id)
    assert.equal(new Set(ids).size, ids.length)
  })

  it('is fully indexed', () => {
    assert.equal(SEALS_BY_ID.size, SEALS.length)
  })

  it('gives every seal a requirement a learner could act on', () => {
    for (const seal of SEALS) {
      assert.ok(seal.name.length > 0, `${seal.id} has a name`)
      assert.ok(seal.requirement.length > 10, `${seal.id} explains itself`)
      assert.ok(seal.points > 0, `${seal.id} is worth something`)
    }
  })

  it('awards nothing on empty evidence', () => {
    // The check that matters most: a seal whose predicate is accidentally true
    // of a brand new account devalues the whole set on day one.
    assert.deepEqual(newlyEarnedSeals(emptyEvidence(), new Set()), [])
  })

  it('is reachable: every seal fires for some evidence', () => {
    // A seal that cannot be computed from what the platform records will
    // silently never fire, and nobody notices a reward that does not arrive.
    const exercises = Array.from({ length: 12 }, (_, i) => `ex-${i}`)
    const lessons = Array.from({ length: 4 }, (_, i) => `l-${i}`)
    const everything = evidence({
      passedExercises: new Set(exercises),
      peekedExercises: new Set(),
      failuresBeforePass: new Map([['ex-0', 12]]),
      passedInsideTimebox: new Set(['ex-0']),
      completedModules: new Set(['m1', 'm2']),
      completedLessons: new Set(lessons),
      coursesTouched: new Set(['ai-agents', 'data-engineering']),
      coursesCompleted: new Set(['ai-agents']),
      weeksInARow: 52,
      weeksMet: 60,
      catalogue: { exerciseIds: exercises, lessonIds: lessons },
    })
    const earned = new Set(newlyEarnedSeals(everything, new Set()).map((s) => s.id))
    for (const seal of SEALS) {
      assert.ok(earned.has(seal.id), `${seal.id} never fires`)
    }
  })
})

describe('individual predicates', () => {
  it('first light needs one pass', () => {
    assert.ok(!SEALS_BY_ID.get('first-light')!.earned(emptyEvidence()))
    assert.ok(SEALS_BY_ID.get('first-light')!.earned(evidence({ passedExercises: new Set(['a']) })))
  })

  it('stubborn rewards the long fight, not the quick win', () => {
    const seal = SEALS_BY_ID.get('stubborn')!
    assert.ok(!seal.earned(evidence({ failuresBeforePass: new Map([['a', 9]]) })))
    assert.ok(seal.earned(evidence({ failuresBeforePass: new Map([['a', 10]]) })))
  })

  it('clean run needs a pass with no failure before it', () => {
    const seal = SEALS_BY_ID.get('clean-run')!
    assert.ok(
      !seal.earned(
        evidence({ passedExercises: new Set(['a']), failuresBeforePass: new Map([['a', 3]]) }),
      ),
    )
    assert.ok(seal.earned(evidence({ passedExercises: new Set(['a']) })))
  })

  it('unaided is lost by a single peek', () => {
    const seal = SEALS_BY_ID.get('unaided-module')!
    const base = { completedModules: new Set(['m1']), passedExercises: new Set(['a', 'b']) }
    assert.ok(seal.earned(evidence(base)))
    assert.ok(!seal.earned(evidence({ ...base, peekedExercises: new Set(['b']) })))
  })

  it('every green needs the whole catalogue, and never fires on an empty one', () => {
    const seal = SEALS_BY_ID.get('every-green')!
    assert.ok(
      !seal.earned(
        evidence({ passedExercises: new Set(['a']), catalogue: { exerciseIds: ['a', 'b'], lessonIds: [] } }),
      ),
    )
    assert.ok(
      seal.earned(
        evidence({ passedExercises: new Set(['a', 'b']), catalogue: { exerciseIds: ['a', 'b'], lessonIds: [] } }),
      ),
    )
    // An empty catalogue must not hand out the completionist seal.
    assert.ok(!seal.earned(emptyEvidence()))
  })

  it('polymath needs two different courses', () => {
    const seal = SEALS_BY_ID.get('polymath')!
    assert.ok(!seal.earned(evidence({ coursesTouched: new Set(['ai-agents']) })))
    assert.ok(seal.earned(evidence({ coursesTouched: new Set(['ai-agents', 'data-engineering']) })))
  })

  it('week seals step at 4, 12 and 52 consecutive weeks', () => {
    for (const [id, weeks] of [['four-weeks', 4], ['a-season', 12], ['a-year', 52]] as const) {
      const seal = SEALS_BY_ID.get(id)!
      assert.ok(!seal.earned(evidence({ weeksInARow: weeks - 1 })), `${id} not at ${weeks - 1}`)
      assert.ok(seal.earned(evidence({ weeksInARow: weeks })), `${id} at ${weeks}`)
    }
  })

  it('rewards a single met week without asking for a run', () => {
    const seal = SEALS_BY_ID.get('first-week')!
    assert.ok(!seal.earned(emptyEvidence()))
    assert.ok(seal.earned(evidence({ weeksMet: 1 })))
  })

  it('has no seal that punishes taking days off', () => {
    // The day-streak seals asked a learner never to take two days off in three
    // months. Nothing here should reward unbroken daily attendance.
    for (const seal of SEALS) {
      assert.ok(
        !/\bday(s)? running\b|\bconsecutive days\b/i.test(seal.requirement),
        `${seal.id} asks for consecutive days: ${seal.requirement}`,
      )
    }
  })
})

describe('newlyEarnedSeals', () => {
  it('does not re-award something already held', () => {
    const e = evidence({ passedExercises: new Set(['a']) })
    const first = newlyEarnedSeals(e, new Set())
    assert.ok(first.some((s) => s.id === 'first-light'))

    const again = newlyEarnedSeals(e, new Set(first.map((s) => s.id)))
    assert.deepEqual(again, [])
  })

  it('can be replayed over history to catch up a seal added later', () => {
    // Predicates are pure over evidence rather than hooked to a live event, so
    // a seal introduced next month is awarded to the people who already earned
    // it rather than only to whoever triggers it next.
    const e = evidence({ weeksInARow: 13, weeksMet: 20, passedExercises: new Set(['a']) })
    const held = new Set(['first-light'])
    const caughtUp = newlyEarnedSeals(e, held).map((s) => s.id)
    assert.ok(caughtUp.includes('four-weeks'))
    assert.ok(caughtUp.includes('a-season'))
    assert.ok(!caughtUp.includes('first-light'))
  })
})
