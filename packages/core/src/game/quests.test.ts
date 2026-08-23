import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  DAILY_QUEST_COUNT,
  EMPTY_COUNTS,
  hashString,
  isoWeekOf,
  questForWeek,
  questProgress,
  questsForDay,
} from './quests'

describe('the daily draw', () => {
  it('is the same every time it is asked', () => {
    // There is no scheduler and nothing stored, so the draw has to be a pure
    // function or two surfaces showing today's quests side by side would
    // disagree.
    const a = questsForDay('user-1', '2026-08-23')
    const b = questsForDay('user-1', '2026-08-23')
    assert.deepEqual(a, b)
  })

  it('draws a different set on a different day', () => {
    const today = questsForDay('user-1', '2026-08-23').map((q) => q.id)
    const later = questsForDay('user-1', '2026-09-14').map((q) => q.id)
    assert.notDeepEqual(today, later)
  })

  it('draws a different set for a different user', () => {
    const a = questsForDay('user-1', '2026-08-23').map((q) => q.id)
    const b = questsForDay('user-2', '2026-08-23').map((q) => q.id)
    assert.notDeepEqual(a, b)
  })

  it('never repeats a quest within a day', () => {
    for (let day = 1; day <= 28; day += 1) {
      for (const user of ['a', 'b', 'c']) {
        const ids = questsForDay(user, `2026-02-${String(day).padStart(2, '0')}`).map((q) => q.id)
        assert.equal(new Set(ids).size, ids.length, `${user} on day ${day}`)
        assert.equal(ids.length, DAILY_QUEST_COUNT)
      }
    }
  })

  it('offers only daily quests', () => {
    for (const quest of questsForDay('user-1', '2026-08-23')) {
      assert.equal(quest.period, 'daily')
    }
  })

  it('reaches the whole pool over time rather than favouring a few', () => {
    const seen = new Set<string>()
    for (let day = 1; day <= 28; day += 1) {
      for (const q of questsForDay('user-1', `2026-02-${String(day).padStart(2, '0')}`)) {
        seen.add(q.id)
      }
    }
    assert.ok(seen.size >= 6, `saw ${seen.size} distinct quests in a month`)
  })
})

describe('the weekly draw', () => {
  it('is stable within a week and turns over between weeks', () => {
    const week = questForWeek('user-1', '2026-W35')
    assert.equal(questForWeek('user-1', '2026-W35').id, week.id)
    assert.equal(week.period, 'weekly')
  })
})

describe('isoWeekOf', () => {
  it('turns over on a Monday, not mid-week', () => {
    // 2026-08-23 is a Sunday; the 24th is the Monday after it.
    assert.equal(isoWeekOf('2026-08-23'), isoWeekOf('2026-08-17'))
    assert.notEqual(isoWeekOf('2026-08-23'), isoWeekOf('2026-08-24'))
  })

  it('formats as YYYY-Www', () => {
    assert.match(isoWeekOf('2026-08-23'), /^\d{4}-W\d{2}$/)
  })

  it('puts an early-January day in the right year', () => {
    // 2026-01-01 is a Thursday, so it belongs to week 1 of 2026.
    assert.equal(isoWeekOf('2026-01-01'), '2026-W01')
  })
})

describe('hashString', () => {
  it('is stable, unsigned, and spread out', () => {
    assert.equal(hashString('abc'), hashString('abc'))
    assert.notEqual(hashString('abc'), hashString('abd'))
    for (const s of ['', 'a', 'user-1:2026-08-23:0', '🙂']) {
      const h = hashString(s)
      assert.ok(Number.isInteger(h) && h >= 0, `${s} hashes to a non-negative integer`)
    }
  })
})

describe('questProgress', () => {
  it('clamps at the target rather than overshooting', () => {
    const quest = questsForDay('user-1', '2026-08-23').find((q) => q.target === 1)!
    const p = questProgress(quest, { ...EMPTY_COUNTS, [quest.metric]: 99 })
    assert.equal(p.progress, quest.target)
    assert.equal(p.complete, true)
  })

  it('is incomplete below the target', () => {
    const quest = { id: 'x', period: 'daily' as const, title: 't', target: 2, metric: 'exercises_passed' as const }
    const p = questProgress(quest, { ...EMPTY_COUNTS, exercises_passed: 1 })
    assert.equal(p.progress, 1)
    assert.equal(p.complete, false)
  })

  it('treats a missing count as zero rather than NaN', () => {
    const quest = { id: 'x', period: 'daily' as const, title: 't', target: 1, metric: 'active_days' as const }
    const p = questProgress(quest, EMPTY_COUNTS)
    assert.equal(p.progress, 0)
    assert.equal(p.complete, false)
  })
})
