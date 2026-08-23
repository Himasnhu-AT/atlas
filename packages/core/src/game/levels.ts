/**
 * The level curve and the ranks laid over it.
 *
 * One expression decides how long the whole game feels, so it is worth saying
 * why this one. XP to reach level L is `10(L-1)² + 30(L-1)`, which puts level 2
 * at 40 XP and level 23 at 5500.
 *
 * It was tuned against the shipped content rather than picked. The obvious
 * steeper curve (`25L² + 75L`) lands a straight run through the AI course at
 * level 13 and makes the last level cost more than a whole module, so the back
 * third of a course delivers almost no level-ups, which is exactly where a
 * student most needs one. This curve gives about 23 levels for a course-sized
 * body of work: an early level costs roughly one exercise, a late one about six.
 *
 * Levels are global across courses. Starting a second course should feel like
 * continuing, not like being reset to zero.
 */

const A = 10
const B = 30

/** Total XP needed to reach a level. Level 1 is where everyone starts, at 0. */
export function xpForLevel(level: number): number {
  const n = Math.max(0, Math.floor(level) - 1)
  return A * n * n + B * n
}

/**
 * The level a total buys.
 *
 * Closed form rather than a loop, so this is safe to call on a leaderboard row
 * by row. Solving `A·n² + B·n = xp` for n and flooring lands on the right level
 * or one either side of it, which the two corrections settle; floating point is
 * the only reason they are needed.
 */
export function levelForXp(xp: number): number {
  if (!Number.isFinite(xp) || xp <= 0) return 1

  let n = Math.floor((-B + Math.sqrt(B * B + 4 * A * xp)) / (2 * A))
  while (A * (n + 1) * (n + 1) + B * (n + 1) <= xp) n += 1
  while (n > 0 && A * n * n + B * n > xp) n -= 1
  return n + 1
}

/**
 * A rank is three levels, and the last one is open ended.
 *
 * The names are the atlas's own, and deliberately say nothing about a subject.
 * They used to be drawn from the AI course (Toolwright, Archivist), which reads
 * well until a student earns "Archivist" for finishing a course on Rust.
 */
export interface Rank {
  /** 1-based tier, rendered as a roman numeral on the stamp. */
  tier: number
  name: string
  /** First level in this tier. */
  fromLevel: number
}

export const RANKS: readonly Rank[] = [
  { tier: 1, name: 'Wanderer', fromLevel: 1 },
  { tier: 2, name: 'Wayfarer', fromLevel: 4 },
  { tier: 3, name: 'Pathfinder', fromLevel: 7 },
  { tier: 4, name: 'Surveyor', fromLevel: 10 },
  { tier: 5, name: 'Chartwright', fromLevel: 13 },
  { tier: 6, name: 'Cartographer', fromLevel: 16 },
  { tier: 7, name: 'Navigator', fromLevel: 19 },
  { tier: 8, name: 'Magister', fromLevel: 22 },
]

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII']

export function romanFor(tier: number): string {
  return ROMAN[tier - 1] ?? String(tier)
}

export function rankForLevel(level: number): Rank {
  let found = RANKS[0]!
  for (const rank of RANKS) {
    if (level >= rank.fromLevel) found = rank
  }
  return found
}

/** Everything a progress bar needs, derived from one number. */
export interface LevelProgress {
  level: number
  rank: Rank
  totalXp: number
  /** XP earned inside the current level. */
  intoLevel: number
  /** XP the current level costs end to end. */
  levelSpan: number
  /** XP still to earn before the next level. */
  toNextLevel: number
  /** Total XP at which the next level arrives. */
  nextLevelAt: number
  /** 0 to 1, for a bar. */
  fraction: number
}

export function levelProgress(totalXp: number): LevelProgress {
  const xp = Math.max(0, Math.floor(totalXp))
  const level = levelForXp(xp)
  const start = xpForLevel(level)
  const nextLevelAt = xpForLevel(level + 1)
  const levelSpan = nextLevelAt - start
  const intoLevel = xp - start

  return {
    level,
    rank: rankForLevel(level),
    totalXp: xp,
    intoLevel,
    levelSpan,
    toNextLevel: nextLevelAt - xp,
    nextLevelAt,
    fraction: levelSpan === 0 ? 0 : intoLevel / levelSpan,
  }
}
