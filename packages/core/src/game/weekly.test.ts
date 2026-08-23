import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  DEFAULT_TARGET,
  MAX_TARGET,
  MIN_TARGET,
  DAILY_BOARD_CAP,
  boardScore,
  clampTarget,
  weekStartOf,
  weeklyProgress,
} from './weekly'

const active = (...days: string[]) => days.map((day) => ({ day, lessonsTouched: 1, attempts: 0 }))

// 2026-08-17 is a Monday, so this week runs 17th to 23rd.
const MONDAY = '2026-08-17'
const SUNDAY = '2026-08-23'

describe('weekStartOf', () => {
  it('finds the Monday of any day in the week', () => {
    for (const day of ['2026-08-17', '2026-08-19', '2026-08-23']) {
      assert.equal(weekStartOf(day), MONDAY, day)
    }
  })

  it('treats Sunday as the end of a week, not the start', () => {
    assert.equal(weekStartOf('2026-08-24'), '2026-08-24', 'the next Monday')
    assert.notEqual(weekStartOf(SUNDAY), weekStartOf('2026-08-24'))
  })

  it('crosses a year boundary', () => {
    assert.equal(weekStartOf('2027-01-01'), '2026-12-28')
  })
})

describe('clampTarget', () => {
  it('keeps a target within a week', () => {
    assert.equal(clampTarget(0), MIN_TARGET)
    assert.equal(clampTarget(-3), MIN_TARGET)
    assert.equal(clampTarget(99), MAX_TARGET)
    assert.equal(clampTarget(3), 3)
  })

  it('falls back rather than producing NaN', () => {
    assert.equal(clampTarget(Number.NaN), DEFAULT_TARGET)
  })
})

describe('weeklyProgress', () => {
  it('counts only days inside the current week', () => {
    const p = weeklyProgress(
      active('2026-08-14', '2026-08-18', '2026-08-20'),
      SUNDAY,
      3,
    )
    assert.equal(p.daysActive, 2, 'the 14th is the previous week')
    assert.equal(p.met, false)
  })

  it('meets the target when enough days are worked', () => {
    const p = weeklyProgress(active('2026-08-18', '2026-08-20', '2026-08-22'), SUNDAY, 3)
    assert.equal(p.daysActive, 3)
    assert.equal(p.met, true)
  })

  it('survives a bad day, which is the entire point', () => {
    // Two hours on Saturday and nothing else all week still meets a target of
    // one, where a daily streak would have been destroyed on Tuesday.
    const p = weeklyProgress(active('2026-08-22'), SUNDAY, 1)
    assert.equal(p.met, true)
  })

  it('excludes the current week from the run behind it', () => {
    // A count that included a week still in progress would drop to zero every
    // Monday morning, which is streak anxiety in weekly clothing.
    const days = active(
      '2026-08-10', '2026-08-11', '2026-08-12',
      '2026-08-17',
    )
    const p = weeklyProgress(days, '2026-08-17', 3)
    assert.equal(p.daysActive, 1, 'Monday of this week')
    assert.equal(p.met, false, 'this week is not done')
    assert.equal(p.weeksInARow, 1, 'last week still counts')
  })

  it('counts consecutive met weeks and stops at the first miss', () => {
    const days = active(
      // three weeks back: met
      '2026-08-03', '2026-08-04', '2026-08-05',
      // two weeks back: missed, only one day
      '2026-08-11',
      // last week: met
      '2026-08-17', '2026-08-18', '2026-08-19',
    )
    const p = weeklyProgress(days, '2026-08-26', 3)
    assert.equal(p.weeksInARow, 1, 'stops at the missed week')
    assert.equal(p.bestWeeks, 1)
  })

  it('reports a best run that is not the current one', () => {
    const days = active(
      '2026-07-06', '2026-07-07', '2026-07-08',
      '2026-07-13', '2026-07-14', '2026-07-15',
      '2026-07-20', '2026-07-21', '2026-07-22',
      // a gap, then one recent week
      '2026-08-17', '2026-08-18', '2026-08-19',
    )
    const p = weeklyProgress(days, '2026-08-26', 3)
    assert.equal(p.weeksInARow, 1)
    assert.equal(p.bestWeeks, 3)
  })

  it('is empty and calm with no activity at all', () => {
    const p = weeklyProgress([], SUNDAY, 3)
    assert.equal(p.daysActive, 0)
    assert.equal(p.met, false)
    assert.equal(p.weeksInARow, 0)
    assert.equal(p.bestWeeks, 0)
  })

  it('ignores a logged day with nothing in it', () => {
    const p = weeklyProgress(
      [{ day: '2026-08-18', lessonsTouched: 0, attempts: 0 }, ...active('2026-08-19')],
      SUNDAY,
      2,
    )
    assert.equal(p.daysActive, 1)
  })

  it('counts a day of attempts with no lesson', () => {
    const p = weeklyProgress([{ day: '2026-08-19', lessonsTouched: 0, attempts: 4 }], SUNDAY, 1)
    assert.equal(p.met, true)
  })

  it('never counts a day twice however many rows it has', () => {
    const p = weeklyProgress(
      [...active('2026-08-19'), ...active('2026-08-19'), ...active('2026-08-20')],
      SUNDAY,
      3,
    )
    assert.equal(p.daysActive, 2)
  })

  it('clamps the target it was handed', () => {
    assert.equal(weeklyProgress([], SUNDAY, 99).target, MAX_TARGET)
  })
})

describe('boardScore', () => {
  it('passes an ordinary week through untouched', () => {
    assert.equal(boardScore({ '2026-08-17': 180, '2026-08-19': 420, '2026-08-22': 96 }), 696)
  })

  it('clamps a single impossible day', () => {
    // Every exercise in the catalogue posted as a pass in one afternoon.
    assert.equal(boardScore({ '2026-08-17': 60_000 }), DAILY_BOARD_CAP)
  })

  it('clamps per day, so the same total cannot be spread around it', () => {
    const spread = { '2026-08-17': 60_000, '2026-08-18': 60_000, '2026-08-19': 60_000 }
    assert.equal(boardScore(spread), DAILY_BOARD_CAP * 3)
  })

  it('still lets a genuinely heavy day outscore a light one', () => {
    assert.ok(
      boardScore({ '2026-08-17': 1_500 }) > boardScore({ '2026-08-17': 200 }),
      'the cap must not flatten honest effort',
    )
  })

  it('ignores a negative, which no award can be anyway', () => {
    assert.equal(boardScore({ '2026-08-17': -50, '2026-08-18': 20 }), 20)
  })
})
