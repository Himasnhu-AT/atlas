import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { MAX_FREEZES, freezesEarned, streakState } from './streak'

/** Active days from `YYYY-MM-DD` strings. */
const active = (...days: string[]) =>
  days.map((day) => ({ day, lessonsTouched: 1, attempts: 0 }))

const TODAY = '2026-08-23'

describe('streakState without freezes', () => {
  it('counts a run ending today', () => {
    const s = streakState(active('2026-08-21', '2026-08-22', '2026-08-23'), TODAY)
    assert.equal(s.days, 3)
    assert.equal(s.rawDays, 3)
  })

  it('still counts a run ending yesterday', () => {
    // A streak should not read as broken because the learner has not opened the
    // app yet this morning.
    const s = streakState(active('2026-08-21', '2026-08-22'), TODAY)
    assert.equal(s.days, 2)
  })

  it('is zero when the last active day is older than yesterday', () => {
    assert.equal(streakState(active('2026-08-20'), TODAY).days, 0)
  })

  it('is zero with no activity at all', () => {
    assert.equal(streakState([], TODAY).days, 0)
  })

  it('ignores a day that was logged but had nothing in it', () => {
    const s = streakState(
      [{ day: TODAY, lessonsTouched: 0, attempts: 0 }, ...active('2026-08-22')],
      TODAY,
    )
    assert.equal(s.days, 1, 'yesterday only')
  })

  it('counts a day with attempts but no lessons', () => {
    const s = streakState([{ day: TODAY, lessonsTouched: 0, attempts: 3 }], TODAY)
    assert.equal(s.days, 1)
  })
})

describe('streakState with freezes', () => {
  it('bridges a single missed day', () => {
    // Mon Tue [missed Wed] Thu Fri, today Fri.
    const s = streakState(
      active('2026-08-17', '2026-08-18', '2026-08-20', '2026-08-21'),
      '2026-08-21',
      1,
    )
    assert.equal(s.days, 5, 'four active days plus the frozen one')
    assert.equal(s.rawDays, 2, 'the strict streak is only Thu and Fri')
    assert.equal(s.freezesSpent, 1)
    assert.equal(s.freezesAvailable, 0)
  })

  it('does not bridge two missed days in a row, whatever is in hand', () => {
    // A freeze covers an off day, not an off week. Spending two to span a gap
    // would make "100 day streak" mean something a reader would not recognise.
    const s = streakState(active('2026-08-17', '2026-08-20', '2026-08-21'), '2026-08-21', 3)
    assert.equal(s.days, 2, 'stops at the two-day gap')
    assert.equal(s.freezesSpent, 0)
  })

  it('does not spend a freeze it does not have', () => {
    const s = streakState(active('2026-08-19', '2026-08-21'), '2026-08-21', 0)
    assert.equal(s.days, 1)
    assert.equal(s.freezesSpent, 0)
  })

  it('spends several across separate gaps', () => {
    // Fri [x] Sun [x] Tue, today Tue.
    const s = streakState(active('2026-08-17', '2026-08-19', '2026-08-21'), '2026-08-21', 2)
    assert.equal(s.days, 5)
    assert.equal(s.freezesSpent, 2)
  })

  it('never spends more than the cap even if handed more', () => {
    const s = streakState(
      active('2026-08-13', '2026-08-15', '2026-08-17', '2026-08-19', '2026-08-21'),
      '2026-08-21',
      99,
    )
    assert.equal(s.freezesSpent, MAX_FREEZES)
  })

  it('never reports a frozen streak shorter than the strict one', () => {
    const days = active('2026-08-19', '2026-08-21', '2026-08-22', '2026-08-23')
    const cold = streakState(days, TODAY, 0)
    const warm = streakState(days, TODAY, 2)
    assert.ok(warm.days >= cold.days)
    assert.equal(warm.rawDays, cold.days)
  })

  it('crosses a month boundary', () => {
    const s = streakState(active('2026-07-30', '2026-07-31', '2026-08-01'), '2026-08-01')
    assert.equal(s.days, 3)
  })
})

describe('freezesEarned', () => {
  it('gives one per seven active days, from lifetime activity', () => {
    // Lifetime rather than the current run, so someone who has shown up for
    // months is not defenceless the day after a streak finally breaks.
    assert.equal(freezesEarned(active()), 0)
    assert.equal(freezesEarned(Array.from({ length: 6 }, (_, i) => ({ day: `2026-01-0${i + 1}`, lessonsTouched: 1, attempts: 0 }))), 0)
    assert.equal(freezesEarned(Array.from({ length: 14 }, (_, i) => ({ day: `2026-01-${String(i + 1).padStart(2, '0')}`, lessonsTouched: 1, attempts: 0 }))), 2)
  })

  it('caps', () => {
    const many = Array.from({ length: 200 }, (_, i) => ({
      day: `2026-01-${String((i % 28) + 1).padStart(2, '0')}`,
      lessonsTouched: 1,
      attempts: 0,
    }))
    assert.equal(freezesEarned(many), MAX_FREEZES)
  })

  it('does not count an empty day', () => {
    const days = Array.from({ length: 14 }, (_, i) => ({
      day: `2026-01-${String(i + 1).padStart(2, '0')}`,
      lessonsTouched: 0,
      attempts: 0,
    }))
    assert.equal(freezesEarned(days), 0)
  })
})
