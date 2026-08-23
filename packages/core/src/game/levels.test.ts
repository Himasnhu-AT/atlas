import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { RANKS, levelForXp, levelProgress, rankForLevel, romanFor, xpForLevel } from './levels'

describe('the level curve', () => {
  it('starts everyone at level 1 with no XP', () => {
    assert.equal(xpForLevel(1), 0)
    assert.equal(levelForXp(0), 1)
  })

  it('puts the second level within a first session', () => {
    // Foundations lesson 1 (12) + lesson 2 (15) + check-your-setup (20 + 25%
    // no-peek + 15% first-run = 28) = 55. Level 2 has to land inside that, or
    // the first reward arrives after an hour instead of after the first
    // passing test.
    assert.equal(xpForLevel(2), 40)
    assert.equal(levelForXp(55), 2)
  })

  it('agrees with itself at every boundary', () => {
    for (let level = 1; level <= 60; level += 1) {
      const at = xpForLevel(level)
      assert.equal(levelForXp(at), level, `exactly at the threshold for ${level}`)
      assert.equal(levelForXp(at + 1), level, `one past the threshold for ${level}`)
      if (level > 1) {
        assert.equal(levelForXp(at - 1), level - 1, `one short of the threshold for ${level}`)
      }
    }
  })

  it('never gets cheaper as it goes up', () => {
    let previous = 0
    for (let level = 2; level <= 60; level += 1) {
      const cost = xpForLevel(level) - xpForLevel(level - 1)
      assert.ok(cost > previous, `level ${level} costs ${cost}, level ${level - 1} cost ${previous}`)
      previous = cost
    }
  })

  it('keeps a late level reachable', () => {
    // The curve this replaced made the last level of a course cost more than a
    // whole module. An exercise averages about 79 XP, so a level should stay
    // under roughly ten of them well past the end of one course.
    const cost = xpForLevel(24) - xpForLevel(23)
    assert.ok(cost < 79 * 10, `level 24 costs ${cost}`)
  })

  it('lands a straight run through the AI course around level 23', () => {
    // 1777 lesson + 2762 exercise + 1375 module, computed from the shipped
    // frontmatter. If content changes enough to move this, the curve should be
    // reconsidered rather than the number quietly updated.
    assert.equal(levelForXp(5914), 23)
    assert.equal(levelForXp(7019), 26)
  })

  it('treats nonsense totals as level 1 rather than NaN', () => {
    assert.equal(levelForXp(-5), 1)
    assert.equal(levelForXp(Number.NaN), 1)
    assert.equal(levelForXp(Number.POSITIVE_INFINITY), 1)
  })
})

describe('ranks', () => {
  it('covers every level with exactly one rank', () => {
    for (let level = 1; level <= 40; level += 1) {
      const rank = rankForLevel(level)
      assert.ok(rank, `level ${level} has a rank`)
      assert.ok(level >= rank.fromLevel)
    }
  })

  it('is ordered and gapless', () => {
    for (let i = 1; i < RANKS.length; i += 1) {
      assert.equal(RANKS[i]!.tier, RANKS[i - 1]!.tier + 1)
      assert.equal(RANKS[i]!.fromLevel, RANKS[i - 1]!.fromLevel + 3)
    }
  })

  it('opens on Wanderer and tops out on Magister', () => {
    assert.equal(rankForLevel(1).name, 'Wanderer')
    assert.equal(rankForLevel(23).name, 'Magister')
    assert.equal(rankForLevel(999).name, 'Magister')
  })

  it('names a tier with a numeral', () => {
    assert.equal(romanFor(1), 'I')
    assert.equal(romanFor(8), 'VIII')
  })

  it('says nothing about a subject', () => {
    // Ranks were once drawn from the AI course, which reads badly the moment
    // someone earns "Archivist" for finishing a course on Rust.
    //
    // Whole words, not substrings: "Cartographer" contains "graph" and is map
    // vocabulary rather than a reference to state graphs.
    const subjectWords = new Set([
      'agent', 'agents', 'tool', 'toolwright', 'prompt', 'prompter', 'rag',
      'graph', 'llm', 'data', 'rust', 'archivist', 'marshal', 'scribe',
    ])
    for (const rank of RANKS) {
      for (const word of rank.name.toLowerCase().split(/[^a-z]+/).filter(Boolean)) {
        assert.ok(!subjectWords.has(word), `${rank.name} names a subject: ${word}`)
      }
    }
  })
})

describe('levelProgress', () => {
  it('reports a fraction inside the current level', () => {
    const p = levelProgress(40)
    assert.equal(p.level, 2)
    assert.equal(p.intoLevel, 0)
    assert.equal(p.fraction, 0)

    const half = levelProgress(40 + (xpForLevel(3) - xpForLevel(2)) / 2)
    assert.equal(half.level, 2)
    assert.equal(half.fraction, 0.5)
  })

  it('always has toNextLevel plus intoLevel equal to the span', () => {
    for (const xp of [0, 1, 39, 40, 100, 1234, 5914, 20000]) {
      const p = levelProgress(xp)
      assert.equal(p.intoLevel + p.toNextLevel, p.levelSpan, `at ${xp}`)
      assert.ok(p.fraction >= 0 && p.fraction < 1, `fraction in range at ${xp}`)
    }
  })
})
