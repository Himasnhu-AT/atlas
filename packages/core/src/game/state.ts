import { z } from 'zod'

/**
 * The one shape both apps render the game from.
 *
 * `GET /api/game` returns exactly this, in one request, the way `/api/progress`
 * returns one snapshot. Every number in it is derived server-side from the XP
 * ledger and the progress rows; none of it is ever sent up by a client.
 */

export const RankState = z.object({
  tier: z.number().int().min(1),
  name: z.string(),
  roman: z.string(),
})
export type RankState = z.infer<typeof RankState>

export const LevelState = z.object({
  level: z.number().int().min(1),
  totalXp: z.number().int().nonnegative(),
  intoLevel: z.number().int().nonnegative(),
  levelSpan: z.number().int().nonnegative(),
  toNextLevel: z.number().int().nonnegative(),
  nextLevelAt: z.number().int().nonnegative(),
  rank: RankState,
})
export type LevelState = z.infer<typeof LevelState>

/**
 * The week against the target the learner set for themselves.
 *
 * Not a daily streak. See `weekly.ts` for why this product does not have one.
 */
export const WeeklyTarget = z.object({
  /** Days a week the learner asked of themselves. */
  target: z.number().int().min(1).max(7),
  daysActive: z.number().int().min(0).max(7),
  met: z.boolean(),
  /** Monday of the current week, `YYYY-MM-DD`. */
  weekStart: z.string(),
  /** Completed weeks behind this one whose target was met. */
  weeksInARow: z.number().int().nonnegative(),
  bestWeeks: z.number().int().nonnegative(),
  /** False until the learner has chosen a target rather than been given one. */
  chosen: z.boolean(),
})
export type WeeklyTarget = z.infer<typeof WeeklyTarget>

export const QuestState = z.object({
  id: z.string(),
  period: z.enum(['daily', 'weekly']),
  title: z.string(),
  target: z.number().int().positive(),
  progress: z.number().int().nonnegative(),
  complete: z.boolean(),
  /** Already claimed, so it pays nothing further. */
  claimed: z.boolean(),
  points: z.number().int().positive(),
  /** The key `POST /api/game/quests/claim` expects. */
  claimKey: z.string(),
})
export type QuestState = z.infer<typeof QuestState>

export const SealState = z.object({
  id: z.string(),
  name: z.string(),
  requirement: z.string(),
  points: z.number().int().nonnegative(),
  earnedAt: z.iso.datetime().optional(),
})
export type SealState = z.infer<typeof SealState>

/** Per-course completion, since progress is per course even though XP is not. */
export const CourseStanding = z.object({
  courseId: z.string(),
  xp: z.number().int().nonnegative(),
  lessonsCompleted: z.number().int().nonnegative(),
  lessonsTotal: z.number().int().nonnegative(),
  exercisesPassed: z.number().int().nonnegative(),
  exercisesTotal: z.number().int().nonnegative(),
  modulesCompleted: z.number().int().nonnegative(),
  modulesTotal: z.number().int().nonnegative(),
})
export type CourseStanding = z.infer<typeof CourseStanding>

export const GameState = z.object({
  level: LevelState,
  week: WeeklyTarget,
  quests: z.array(QuestState),
  /** Every seal, earned or not, so the ledger can show the blanks. */
  seals: z.array(SealState),
  courses: z.array(CourseStanding),
  leaderboardOptIn: z.boolean(),
  /** The rules version the stored awards were computed under. */
  rulesVersion: z.number().int().positive(),
})
export type GameState = z.infer<typeof GameState>

export const LeaderboardRow = z.object({
  displayName: z.string(),
  level: z.number().int().min(1),
  weeklyXp: z.number().int().nonnegative(),
  /** True for the requesting user's own row. */
  you: z.boolean(),
})
export type LeaderboardRow = z.infer<typeof LeaderboardRow>

export const Leaderboard = z.object({
  isoWeek: z.string(),
  rows: z.array(LeaderboardRow),
})
export type Leaderboard = z.infer<typeof Leaderboard>

/** Bodies. As everywhere else, none of them carries a user id or a point value. */

export const ClaimQuest = z.object({ claimKey: z.string().max(120) })
export type ClaimQuest = z.infer<typeof ClaimQuest>

export const UpdateGameSettings = z.object({
  leaderboardOptIn: z.boolean().optional(),
  /** Days a week. The learner sets this; nothing else may. */
  weeklyTarget: z.number().int().min(1).max(7).optional(),
})
export type UpdateGameSettings = z.infer<typeof UpdateGameSettings>
