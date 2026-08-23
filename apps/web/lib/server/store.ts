import 'server-only'

import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'

import type {
  ActivityDay,
  ExerciseState,
  LessonProgress,
  ModuleProgress,
  NewAttempt,
  ProgressSnapshot,
  User,
} from '@atlas/core'
import { boardScore } from '@atlas/core'

/**
 * The only module that talks to persistent storage.
 *
 * Two implementations behind one interface. When SUPABASE_URL and
 * SUPABASE_SERVICE_ROLE_KEY are set, everything goes to Postgres. When they are
 * not, it goes to a JSON file under .data/ so the app runs with zero
 * configuration.
 *
 * Both live server-side. The service role key never leaves this process, and no
 * client ever holds a database credential, which is why the API is the security
 * boundary rather than row level security.
 */

export interface StoredUser extends User {
  passwordHash: string
  passwordSalt: string
  /**
   * What this account may open.
   *
   * There is no payment provider behind this yet, and deliberately so: a
   * free/paid boundary is easy to add once there is something worth charging
   * for, and a Stripe integration written before then is a guess with webhooks
   * attached. The field exists so the boundary is enforced in one place from
   * the start rather than retrofitted through every route later.
   */
  plan?: 'free' | 'member'
}

/** One row of the XP ledger, as the store writes it. */
export interface StoredAward {
  awardKey: string
  kind: string
  points: number
  courseId?: string
  rulesVersion: number
  occurredAt: string
  awardedAt: string
}

/**
 * What a learner has done with one exercise, in aggregate.
 *
 * The first-run bonus and two seals read failure counts, so this has to be
 * durable. `LocalStore` keeps these as counters because it truncates its attempt
 * log to stay a reasonable size on disk; Supabase derives them from the full
 * append-only log, which is complete there. Same numbers, different source.
 */
export interface ExerciseStats {
  exerciseId: string
  passes: number
  failures: number
  /** Failed runs recorded before the first pass. */
  failuresBeforePass: number
  firstPassedAt?: string
  /** Fastest passing run, for the inside-the-timebox seal. */
  bestPassDurationMs?: number
}

export interface GameRecord {
  totalXp: number
  /** Days a week the learner asked of themselves. */
  weeklyTarget: number
  /**
   * Whether the learner actually chose that target.
   *
   * A default is offered so the surface has something to show, but a goal
   * nobody set is a target imposed with extra steps, so the UI says so until
   * they pick one.
   */
  weeklyTargetChosen: boolean
  /** Longest run of weeks whose target was met. */
  bestWeeks: number
  leaderboardOptIn: boolean
  /**
   * Set by hand to take somebody off the board without touching their account.
   *
   * The threat model says no automated banning: `stdout_tail` is already
   * recorded and a human settles a case in a minute, whereas a heuristic
   * accuses people who genuinely wrote the same solution.
   */
  leaderboardExcluded: boolean
  timezone: string
}

export const EMPTY_GAME: GameRecord = {
  totalXp: 0,
  weeklyTarget: 3,
  weeklyTargetChosen: false,
  bestWeeks: 0,
  leaderboardOptIn: false,
  leaderboardExcluded: false,
  timezone: 'UTC',
}

/** A paired device. Named, listable, and revocable. */
export interface StoredDevice {
  id: string
  userId: string
  name: string
  platform: string
  appVersion: string
  createdAt: string
  lastSeenAt: string
  revokedAt?: string
}

/**
 * A pairing in flight.
 *
 * Kept apart from `devices` because the lifetimes differ by orders of
 * magnitude: a pairing expires in ten minutes and a device lives for years.
 * Mixing them means an index mostly full of dead rows.
 */
export interface StoredPairing {
  /** SHA-256 of the device code. The code itself is never stored. */
  deviceCodeHash: string
  /** Eight readable characters the person types into the browser. */
  userCode: string
  name: string
  platform: string
  appVersion: string
  createdAt: string
  expiresAt: string
  /** Set when a signed-in browser approves it. */
  userId?: string
  approvedAt?: string
}

export interface LeaderboardEntry {
  userId: string
  displayName: string
  weeklyXp: number
  totalXp: number
}

export interface Store {
  findUserByEmail(email: string): Promise<StoredUser | null>
  findUserById(id: string): Promise<StoredUser | null>
  createUser(user: StoredUser): Promise<void>
  touchUser(id: string): Promise<void>

  progressFor(userId: string): Promise<ProgressSnapshot>
  upsertLessonProgress(userId: string, progress: LessonProgress): Promise<void>
  upsertModuleProgress(userId: string, progress: ModuleProgress): Promise<void>
  recordActivity(userId: string, day: string, kind: 'lesson' | 'attempt'): Promise<void>

  exerciseState(userId: string, exerciseId: string): Promise<ExerciseState | null>
  saveExerciseState(userId: string, state: ExerciseState): Promise<void>

  /**
   * Records one run. Returns false when `clientEventId` was already applied,
   * which is how a replayed outbox batch is stopped from counting twice.
   */
  recordAttempt(
    userId: string,
    attempt: NewAttempt,
    clientEventId?: string,
  ): Promise<boolean>
  exerciseStats(userId: string): Promise<ExerciseStats[]>

  gameFor(userId: string): Promise<GameRecord>
  updateGame(userId: string, patch: Partial<GameRecord>): Promise<void>

  /**
   * Write one award, or do nothing because it was already written.
   *
   * Returns the points actually granted, so a caller can tell a first
   * completion from a replay without a second read. The whole idempotency story
   * lives behind this one boolean: the key is unique per user, and the cached
   * total only moves when the insert did.
   */
  awardXp(userId: string, award: StoredAward): Promise<number>
  awardsFor(userId: string): Promise<StoredAward[]>

  sealsFor(userId: string): Promise<{ sealId: string; earnedAt: string }[]>
  grantSeal(userId: string, sealId: string, courseId?: string): Promise<boolean>

  /** XP received (not merely occurred) since `since`, for opted-in users. */
  weeklyLeaderboard(since: string, limit: number): Promise<LeaderboardEntry[]>

  devicesFor(userId: string): Promise<StoredDevice[]>
  findDevice(deviceId: string): Promise<StoredDevice | null>
  createDevice(device: StoredDevice): Promise<void>
  touchDevice(deviceId: string): Promise<void>
  revokeDevice(userId: string, deviceId: string): Promise<boolean>

  createPairing(pairing: StoredPairing): Promise<void>
  findPairingByUserCode(userCode: string): Promise<StoredPairing | null>
  findPairingByCodeHash(hash: string): Promise<StoredPairing | null>
  approvePairing(userCode: string, userId: string): Promise<boolean>
  deletePairing(hash: string): Promise<void>
}

export function hasSupabase(): boolean {
  return Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY)
}

/** Storage mode, surfaced in the UI so nobody is confused about where data went. */
export function storageMode(): 'supabase' | 'local' {
  return hasSupabase() ? 'supabase' : 'local'
}

// Local file store.

interface LocalData {
  users: Record<string, StoredUser>
  lessonProgress: Record<string, LessonProgress[]>
  moduleProgress: Record<string, ModuleProgress[]>
  exerciseState: Record<string, ExerciseState[]>
  attempts: Record<string, (NewAttempt & { id: string; createdAt: string })[]>
  /** Durable per-exercise counters, because `attempts` above is truncated. */
  stats: Record<string, Record<string, ExerciseStats>>
  /**
   * Client event ids already applied, newest last.
   *
   * Award keys stop a replayed batch paying twice, but they do not stop it
   * being *recorded* twice, and the attempt counters are what the first-run
   * bonus and two seals read. Without this a plain 5xx retry inflates the
   * failure count: five replays of two genuine failures mints Stubborn.
   */
  seenEvents: Record<string, string[]>
  activity: Record<string, ActivityDay[]>
  awards: Record<string, StoredAward[]>
  game: Record<string, GameRecord>
  seals: Record<string, { sealId: string; courseId?: string; earnedAt: string }[]>
  devices: Record<string, StoredDevice>
  pairings: Record<string, StoredPairing>
}

const EMPTY: LocalData = {
  users: {},
  lessonProgress: {},
  moduleProgress: {},
  exerciseState: {},
  attempts: {},
  stats: {},
  seenEvents: {},
  activity: {},
  awards: {},
  game: {},
  seals: {},
  devices: {},
  pairings: {},
}

const DATA_DIR = path.join(process.cwd(), '.data')
const DATA_FILE = path.join(DATA_DIR, 'store.json')

class LocalStore implements Store {
  private cache: LocalData | null = null
  /**
   * Modification time of the file the cache was built from.
   *
   * The cache used to have no invalidation at all, which is wrong for a reason
   * that is invisible until something reads and something else writes: Next
   * builds route handlers and pages into separate module graphs, so each gets
   * its own `LocalStore` and its own copy of this cache. Whichever one did not
   * perform a write went on serving its first read forever. The symptom was a
   * page insisting a learner had not joined the leaderboard while the API,
   * asked directly, said they had.
   *
   * Supabase has never had this problem because it holds no state here. The
   * zero-config local path is the documented default, so it cannot be the one
   * that quietly lies.
   */
  private cachedAt = 0
  /** Serializes writes so two concurrent requests cannot clobber each other. */
  private queue: Promise<unknown> = Promise.resolve()

  private async read(): Promise<LocalData> {
    let mtime = 0
    try {
      mtime = (await stat(DATA_FILE)).mtimeMs
    } catch {
      // No file yet. A cache built from nothing is still valid.
    }

    if (this.cache && mtime === this.cachedAt) return this.cache

    let loaded: LocalData
    try {
      loaded = { ...EMPTY, ...JSON.parse(await readFile(DATA_FILE, 'utf8')) }
    } catch {
      // No file yet, or it was corrupted. Either way, start clean rather than
      // taking the whole server down on a first run.
      loaded = structuredClone(EMPTY)
    }

    this.cache = loaded
    this.cachedAt = mtime
    return loaded
  }

  private write<T>(mutate: (data: LocalData) => T): Promise<T> {
    const next = this.queue.then(async () => {
      const data = await this.read()
      const result = mutate(data)
      await mkdir(DATA_DIR, { recursive: true })
      await writeFile(DATA_FILE, JSON.stringify(data, null, 2))
      // Adopt the file we just wrote, so this instance does not immediately
      // discard the object it has been mutating and re-read its own write.
      try {
        this.cachedAt = (await stat(DATA_FILE)).mtimeMs
      } catch {
        this.cachedAt = 0
      }
      return result
    })
    // Keep the chain alive even if this write threw.
    this.queue = next.catch(() => undefined)
    return next
  }

  async findUserByEmail(email: string) {
    const data = await this.read()
    return (
      Object.values(data.users).find(
        (user) => user.email.toLowerCase() === email.toLowerCase(),
      ) ?? null
    )
  }

  async findUserById(id: string) {
    return (await this.read()).users[id] ?? null
  }

  async createUser(user: StoredUser) {
    await this.write((data) => {
      data.users[user.id] = user
    })
  }

  async touchUser(_id: string) {
    // Last-seen tracking is not interesting without Supabase analytics.
  }

  async progressFor(userId: string): Promise<ProgressSnapshot> {
    const data = await this.read()
    return {
      lessons: data.lessonProgress[userId] ?? [],
      modules: data.moduleProgress[userId] ?? [],
      activity: data.activity[userId] ?? [],
      streakDays: 0,
    }
  }

  async upsertLessonProgress(userId: string, progress: LessonProgress) {
    await this.write((data) => {
      const rows = (data.lessonProgress[userId] ??= [])
      const index = rows.findIndex((row) => row.lessonId === progress.lessonId)
      if (index === -1) rows.push(progress)
      else rows[index] = progress
    })
  }

  async upsertModuleProgress(userId: string, progress: ModuleProgress) {
    await this.write((data) => {
      const rows = (data.moduleProgress[userId] ??= [])
      const index = rows.findIndex((row) => row.moduleId === progress.moduleId)
      if (index === -1) rows.push(progress)
      else rows[index] = progress
    })
  }

  async recordActivity(userId: string, day: string, kind: 'lesson' | 'attempt') {
    await this.write((data) => {
      const rows = (data.activity[userId] ??= [])
      const row = rows.find((entry) => entry.day === day)
      if (row) {
        if (kind === 'lesson') row.lessonsTouched += 1
        else row.attempts += 1
      } else {
        rows.push({
          day,
          lessonsTouched: kind === 'lesson' ? 1 : 0,
          attempts: kind === 'attempt' ? 1 : 0,
        })
      }
    })
  }

  async exerciseState(userId: string, exerciseId: string) {
    const data = await this.read()
    return (
      (data.exerciseState[userId] ?? []).find((row) => row.exerciseId === exerciseId) ?? null
    )
  }

  async saveExerciseState(userId: string, state: ExerciseState) {
    await this.write((data) => {
      const rows = (data.exerciseState[userId] ??= [])
      const index = rows.findIndex((row) => row.exerciseId === state.exerciseId)
      if (index === -1) rows.push(state)
      else rows[index] = state
    })
  }

  async recordAttempt(userId: string, attempt: NewAttempt, clientEventId?: string) {
    let applied = true

    await this.write((data) => {
      // Inside the mutate callback, never before it. `write` serialises through
      // a promise queue, so a check-then-write split across two calls is a race
      // that two draining devices will eventually lose.
      if (clientEventId !== undefined) {
        const seen = (data.seenEvents[userId] ??= [])
        if (seen.includes(clientEventId)) {
          applied = false
          return
        }
        seen.push(clientEventId)
        // Bounded, like the attempt log. A drain carries at most MAX_EVENTS and
        // retries follow within minutes, so this is far more history than a
        // replay can span. Supabase gets a real unique constraint instead.
        if (seen.length > 2000) seen.splice(0, seen.length - 2000)
      }

      const now = new Date().toISOString()
      const rows = (data.attempts[userId] ??= [])
      rows.push({ ...attempt, id: randomUUID(), createdAt: now })
      // An unbounded append-only log in a JSON file is a memory leak with extra
      // steps. Supabase keeps the full history.
      if (rows.length > 500) rows.splice(0, rows.length - 500)

      // Counters, kept separately and never truncated. The log above loses its
      // oldest rows, and the first-run bonus and two seals read failure counts,
      // so deriving them from a truncated log would quietly stop awarding things
      // to exactly the learners who have been here longest.
      const byExercise = (data.stats[userId] ??= {})
      const stat = (byExercise[attempt.exerciseId] ??= {
        exerciseId: attempt.exerciseId,
        passes: 0,
        failures: 0,
        failuresBeforePass: 0,
      })

      if (attempt.passed) {
        stat.passes += 1
        stat.firstPassedAt ??= now
        if (
          stat.bestPassDurationMs === undefined ||
          attempt.durationMs < stat.bestPassDurationMs
        ) {
          stat.bestPassDurationMs = attempt.durationMs
        }
      } else {
        stat.failures += 1
        if (stat.passes === 0) stat.failuresBeforePass += 1
      }
    })

    return applied
  }

  async exerciseStats(userId: string): Promise<ExerciseStats[]> {
    return Object.values((await this.read()).stats[userId] ?? {})
  }

  async gameFor(userId: string): Promise<GameRecord> {
    return { ...EMPTY_GAME, ...(await this.read()).game[userId] }
  }

  async updateGame(userId: string, patch: Partial<GameRecord>) {
    await this.write((data) => {
      data.game[userId] = { ...EMPTY_GAME, ...data.game[userId], ...patch }
    })
  }

  async awardXp(userId: string, award: StoredAward): Promise<number> {
    // The check and the write are both inside `mutate`, which `write()` runs
    // through a promise queue. Doing the lookup outside it and then calling
    // `write()` is the natural way to express this and is a race: two requests
    // for the same award both read "not present" and both append.
    return this.write((data) => {
      const rows = (data.awards[userId] ??= [])
      if (rows.some((row) => row.awardKey === award.awardKey)) return 0

      rows.push(award)
      const game = (data.game[userId] = { ...EMPTY_GAME, ...data.game[userId] })
      game.totalXp += award.points
      return award.points
    })
  }

  async awardsFor(userId: string): Promise<StoredAward[]> {
    return (await this.read()).awards[userId] ?? []
  }

  async sealsFor(userId: string) {
    return (await this.read()).seals[userId] ?? []
  }

  async grantSeal(userId: string, sealId: string, courseId?: string): Promise<boolean> {
    return this.write((data) => {
      const rows = (data.seals[userId] ??= [])
      if (rows.some((row) => row.sealId === sealId)) return false
      rows.push({ sealId, courseId, earnedAt: new Date().toISOString() })
      return true
    })
  }

  async weeklyLeaderboard(since: string, limit: number): Promise<LeaderboardEntry[]> {
    const data = await this.read()
    const rows: LeaderboardEntry[] = []

    for (const [userId, game] of Object.entries(data.game)) {
      if (!game.leaderboardOptIn || game.leaderboardExcluded) continue
      const user = data.users[userId]
      if (!user) continue

      // Grouped by the day the award was received, then each day clamped. See
      // `boardScore`: the cap is on the standing, never on the ledger.
      const byDay: Record<string, number> = {}
      for (const award of data.awards[userId] ?? []) {
        if (award.awardedAt < since) continue
        const day = award.awardedAt.slice(0, 10)
        byDay[day] = (byDay[day] ?? 0) + award.points
      }
      const weeklyXp = boardScore(byDay)

      rows.push({ userId, displayName: user.displayName, weeklyXp, totalXp: game.totalXp })
    }

    return rows.sort((a, b) => b.weeklyXp - a.weeklyXp).slice(0, limit)
  }

  async devicesFor(userId: string): Promise<StoredDevice[]> {
    const data = await this.read()
    return Object.values(data.devices)
      .filter((d) => d.userId === userId)
      .sort((a, b) => b.lastSeenAt.localeCompare(a.lastSeenAt))
  }

  async findDevice(deviceId: string): Promise<StoredDevice | null> {
    return (await this.read()).devices[deviceId] ?? null
  }

  async createDevice(device: StoredDevice) {
    await this.write((data) => {
      data.devices[device.id] = device
    })
  }

  async touchDevice(deviceId: string) {
    await this.write((data) => {
      const device = data.devices[deviceId]
      if (device) device.lastSeenAt = new Date().toISOString()
    })
  }

  async revokeDevice(userId: string, deviceId: string): Promise<boolean> {
    return this.write((data) => {
      const device = data.devices[deviceId]
      // Ownership is checked here rather than by the caller, so a device id
      // guessed from somewhere else revokes nothing.
      if (!device || device.userId !== userId || device.revokedAt) return false
      device.revokedAt = new Date().toISOString()
      return true
    })
  }

  async createPairing(pairing: StoredPairing) {
    await this.write((data) => {
      // Expired pairings are swept on write rather than by a job. There are
      // never many, and a job that has to run for correctness is a job that
      // will one day not run.
      const now = new Date().toISOString()
      for (const [hash, row] of Object.entries(data.pairings)) {
        if (row.expiresAt < now) delete data.pairings[hash]
      }
      data.pairings[pairing.deviceCodeHash] = pairing
    })
  }

  async findPairingByUserCode(userCode: string): Promise<StoredPairing | null> {
    const data = await this.read()
    const now = new Date().toISOString()
    return (
      Object.values(data.pairings).find(
        (row) => row.userCode === userCode && row.expiresAt >= now,
      ) ?? null
    )
  }

  async findPairingByCodeHash(hash: string): Promise<StoredPairing | null> {
    const row = (await this.read()).pairings[hash]
    if (!row) return null
    return row.expiresAt >= new Date().toISOString() ? row : null
  }

  async approvePairing(userCode: string, userId: string): Promise<boolean> {
    return this.write((data) => {
      const now = new Date().toISOString()
      const row = Object.values(data.pairings).find(
        (candidate) => candidate.userCode === userCode && candidate.expiresAt >= now,
      )
      if (!row || row.approvedAt) return false
      row.userId = userId
      row.approvedAt = now
      return true
    })
  }

  async deletePairing(hash: string) {
    await this.write((data) => {
      delete data.pairings[hash]
    })
  }
}

// Supabase store.

class SupabaseStore implements Store {
  private client() {
    // Imported lazily so the local path never loads the SDK.
    const { createClient } = require('@supabase/supabase-js')
    return createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!, {
      auth: { persistSession: false },
    })
  }

  async findUserByEmail(email: string): Promise<StoredUser | null> {
    const { data } = await this.client()
      .from('users')
      .select('*')
      .ilike('email', email)
      .maybeSingle()
    return data ? rowToUser(data) : null
  }

  async findUserById(id: string): Promise<StoredUser | null> {
    const { data } = await this.client().from('users').select('*').eq('id', id).maybeSingle()
    return data ? rowToUser(data) : null
  }

  async createUser(user: StoredUser) {
    const { error } = await this.client().from('users').insert({
      id: user.id,
      email: user.email,
      display_name: user.displayName,
      password_hash: user.passwordHash,
      password_salt: user.passwordSalt,
      created_at: user.createdAt,
      plan: user.plan ?? 'free',
    })
    if (error) throw new Error(error.message)
  }

  async touchUser(id: string) {
    await this.client()
      .from('users')
      .update({ last_seen_at: new Date().toISOString() })
      .eq('id', id)
  }

  async progressFor(userId: string): Promise<ProgressSnapshot> {
    const client = this.client()
    const [lessons, modules, activity] = await Promise.all([
      client.from('lesson_progress').select('*').eq('user_id', userId),
      client.from('module_progress').select('*').eq('user_id', userId),
      client.from('activity_days').select('*').eq('user_id', userId),
    ])

    return {
      lessons: (lessons.data ?? []).map((row: Record<string, unknown>) => ({
        lessonId: row.lesson_id as string,
        moduleId: row.module_id as string,
        status: row.status as LessonProgress['status'],
        secondsSpent: (row.seconds_spent as number) ?? 0,
        startedAt: (row.started_at as string) ?? undefined,
        completedAt: (row.completed_at as string) ?? undefined,
      })),
      modules: (modules.data ?? []).map((row: Record<string, unknown>) => ({
        moduleId: row.module_id as string,
        status: row.status as ModuleProgress['status'],
        lessonsCompleted: (row.lessons_completed as number) ?? 0,
        lessonsTotal: (row.lessons_total as number) ?? 0,
        startedAt: (row.started_at as string) ?? undefined,
        completedAt: (row.completed_at as string) ?? undefined,
      })),
      activity: (activity.data ?? []).map((row: Record<string, unknown>) => ({
        day: row.day as string,
        lessonsTouched: (row.lessons_touched as number) ?? 0,
        attempts: (row.attempts as number) ?? 0,
      })),
      streakDays: 0,
    }
  }

  async upsertLessonProgress(userId: string, progress: LessonProgress) {
    await this.client()
      .from('lesson_progress')
      .upsert(
        {
          user_id: userId,
          lesson_id: progress.lessonId,
          module_id: progress.moduleId,
          status: progress.status,
          seconds_spent: progress.secondsSpent,
          started_at: progress.startedAt,
          completed_at: progress.completedAt,
        },
        { onConflict: 'user_id,lesson_id' },
      )
  }

  async upsertModuleProgress(userId: string, progress: ModuleProgress) {
    await this.client()
      .from('module_progress')
      .upsert(
        {
          user_id: userId,
          module_id: progress.moduleId,
          status: progress.status,
          lessons_completed: progress.lessonsCompleted,
          lessons_total: progress.lessonsTotal,
          started_at: progress.startedAt,
          completed_at: progress.completedAt,
        },
        { onConflict: 'user_id,module_id' },
      )
  }

  async recordActivity(userId: string, day: string, kind: 'lesson' | 'attempt') {
    await this.client().rpc('bump_activity', {
      p_user_id: userId,
      p_day: day,
      p_lessons: kind === 'lesson' ? 1 : 0,
      p_attempts: kind === 'attempt' ? 1 : 0,
    })
  }

  async exerciseState(userId: string, exerciseId: string): Promise<ExerciseState | null> {
    const { data } = await this.client()
      .from('exercise_state')
      .select('*')
      .eq('user_id', userId)
      .eq('exercise_id', exerciseId)
      .maybeSingle()

    if (!data) return null
    return {
      exerciseId: data.exercise_id,
      currentCode: data.current_code ?? '',
      peekedReferenceAt: data.peeked_reference_at ?? undefined,
      updatedAt: data.updated_at,
    }
  }

  async saveExerciseState(userId: string, state: ExerciseState) {
    await this.client()
      .from('exercise_state')
      .upsert(
        {
          user_id: userId,
          exercise_id: state.exerciseId,
          current_code: state.currentCode,
          peeked_reference_at: state.peekedReferenceAt,
          updated_at: state.updatedAt,
        },
        { onConflict: 'user_id,exercise_id' },
      )
  }

  async recordAttempt(userId: string, attempt: NewAttempt, clientEventId?: string) {
    // `unique (user_id, client_event_id)` does the work. `ignoreDuplicates` on a
    // conflict makes a replayed batch a no-op rather than an error, so a device
    // retrying after a 5xx does not have to know what it already sent.
    const { data } = await this.client()
      .from('exercise_attempts')
      .upsert(
        {
          user_id: userId,
          exercise_id: attempt.exerciseId,
          passed: attempt.passed,
          tests_passed: attempt.testsPassed,
          tests_total: attempt.testsTotal,
          duration_ms: attempt.durationMs,
          stdout_tail: attempt.stdoutTail?.slice(-4000),
          client_event_id: clientEventId,
        },
        { onConflict: 'user_id,client_event_id', ignoreDuplicates: true },
      )
      .select('id')

    // `ignoreDuplicates` makes a replay silent rather than an error, so the
    // error field cannot tell them apart. The returned rows can: a duplicate
    // inserts nothing and comes back empty.
    return (data?.length ?? 0) > 0
  }

  /**
   * Derived from the log rather than from counters.
   *
   * `exercise_attempts` is append-only and complete here, and the index on
   * `(user_id, exercise_id, created_at desc)` makes one user's history cheap.
   * `LocalStore` keeps counters instead because its log is truncated.
   */
  async exerciseStats(userId: string): Promise<ExerciseStats[]> {
    const { data } = await this.client()
      .from('exercise_attempts')
      .select('exercise_id, passed, duration_ms, created_at')
      .eq('user_id', userId)
      .order('created_at', { ascending: true })

    const byExercise = new Map<string, ExerciseStats>()
    for (const row of (data ?? []) as Record<string, unknown>[]) {
      const exerciseId = row.exercise_id as string
      let stat = byExercise.get(exerciseId)
      if (!stat) {
        stat = { exerciseId, passes: 0, failures: 0, failuresBeforePass: 0 }
        byExercise.set(exerciseId, stat)
      }

      if (row.passed) {
        stat.passes += 1
        stat.firstPassedAt ??= row.created_at as string
        const duration = (row.duration_ms as number) ?? 0
        if (stat.bestPassDurationMs === undefined || duration < stat.bestPassDurationMs) {
          stat.bestPassDurationMs = duration
        }
      } else {
        stat.failures += 1
        if (stat.passes === 0) stat.failuresBeforePass += 1
      }
    }

    return [...byExercise.values()]
  }

  async gameFor(userId: string): Promise<GameRecord> {
    const { data } = await this.client()
      .from('user_game')
      .select('*')
      .eq('user_id', userId)
      .maybeSingle()

    if (!data) return { ...EMPTY_GAME }
    return {
      totalXp: data.total_xp ?? 0,
      weeklyTarget: data.weekly_target ?? EMPTY_GAME.weeklyTarget,
      weeklyTargetChosen: data.weekly_target_chosen ?? false,
      bestWeeks: data.best_weeks ?? 0,
      leaderboardOptIn: data.leaderboard_opt_in ?? false,
      leaderboardExcluded: data.leaderboard_excluded ?? false,
      timezone: data.timezone ?? 'UTC',
    }
  }

  async updateGame(userId: string, patch: Partial<GameRecord>) {
    const row: Record<string, unknown> = { user_id: userId, updated_at: new Date().toISOString() }
    if (patch.totalXp !== undefined) row.total_xp = patch.totalXp
    if (patch.weeklyTarget !== undefined) row.weekly_target = patch.weeklyTarget
    if (patch.weeklyTargetChosen !== undefined) row.weekly_target_chosen = patch.weeklyTargetChosen
    if (patch.bestWeeks !== undefined) row.best_weeks = patch.bestWeeks
    if (patch.leaderboardOptIn !== undefined) row.leaderboard_opt_in = patch.leaderboardOptIn
    if (patch.leaderboardExcluded !== undefined)
      row.leaderboard_excluded = patch.leaderboardExcluded
    if (patch.timezone !== undefined) row.timezone = patch.timezone

    await this.client().from('user_game').upsert(row, { onConflict: 'user_id' })
  }

  /**
   * One statement, in the database.
   *
   * The insert dedupes on the primary key and the cached total only moves when
   * the insert actually happened. Doing the two here, over two round trips,
   * would let a double-click write one ledger row and add the points twice.
   */
  async awardXp(userId: string, award: StoredAward): Promise<number> {
    const { data, error } = await this.client().rpc('award_xp', {
      p_user_id: userId,
      p_award_key: award.awardKey,
      p_kind: award.kind,
      p_points: award.points,
      p_course_id: award.courseId ?? null,
      p_rules_version: award.rulesVersion,
      p_occurred_at: award.occurredAt,
    })
    if (error) throw new Error(error.message)
    return (data as number) ?? 0
  }

  async awardsFor(userId: string): Promise<StoredAward[]> {
    const { data } = await this.client()
      .from('xp_awards')
      .select('*')
      .eq('user_id', userId)
      .order('awarded_at', { ascending: false })

    return ((data ?? []) as Record<string, unknown>[]).map((row) => ({
      awardKey: row.award_key as string,
      kind: row.kind as string,
      points: (row.points as number) ?? 0,
      courseId: (row.course_id as string) ?? undefined,
      rulesVersion: (row.rules_version as number) ?? 1,
      occurredAt: row.occurred_at as string,
      awardedAt: row.awarded_at as string,
    }))
  }

  async sealsFor(userId: string) {
    const { data } = await this.client()
      .from('user_seals')
      .select('seal_id, earned_at')
      .eq('user_id', userId)

    return ((data ?? []) as Record<string, unknown>[]).map((row) => ({
      sealId: row.seal_id as string,
      earnedAt: row.earned_at as string,
    }))
  }

  async grantSeal(userId: string, sealId: string, courseId?: string): Promise<boolean> {
    const { data, error } = await this.client()
      .from('user_seals')
      .upsert(
        { user_id: userId, seal_id: sealId, course_id: courseId ?? null },
        { onConflict: 'user_id,seal_id', ignoreDuplicates: true },
      )
      .select('seal_id')

    if (error) throw new Error(error.message)
    // `ignoreDuplicates` returns nothing when the row was already there, which
    // is what makes this answer "was this newly granted" rather than "does it
    // exist".
    return ((data ?? []) as unknown[]).length > 0
  }

  async weeklyLeaderboard(since: string, limit: number): Promise<LeaderboardEntry[]> {
    const client = this.client()
    const { data: optedIn } = await client
      .from('user_game')
      .select('user_id, total_xp')
      .eq('leaderboard_opt_in', true)
      .not('leaderboard_excluded', 'is', true)

    const ids = ((optedIn ?? []) as Record<string, unknown>[]).map((r) => r.user_id as string)
    if (ids.length === 0) return []

    const [{ data: awards }, { data: users }] = await Promise.all([
      client
        .from('xp_awards')
        .select('user_id, points, awarded_at')
        .in('user_id', ids)
        .gte('awarded_at', since),
      client.from('users').select('id, display_name').in('id', ids),
    ])

    const names = new Map(
      ((users ?? []) as Record<string, unknown>[]).map((r) => [r.id as string, r.display_name as string]),
    )
    // Per user, per day, then clamped. See `boardScore`: an uncapped week is
    // the one thing a public board makes worth faking.
    const byUserDay = new Map<string, Record<string, number>>()
    for (const row of (awards ?? []) as Record<string, unknown>[]) {
      const id = row.user_id as string
      const day = String(row.awarded_at ?? '').slice(0, 10)
      const days = byUserDay.get(id) ?? {}
      days[day] = (days[day] ?? 0) + ((row.points as number) ?? 0)
      byUserDay.set(id, days)
    }

    const weekly = new Map<string, number>()
    for (const [id, days] of byUserDay) weekly.set(id, boardScore(days))

    return ((optedIn ?? []) as Record<string, unknown>[])
      .map((r) => ({
        userId: r.user_id as string,
        displayName: names.get(r.user_id as string) ?? 'Someone',
        weeklyXp: weekly.get(r.user_id as string) ?? 0,
        totalXp: (r.total_xp as number) ?? 0,
      }))
      .sort((a, b) => b.weeklyXp - a.weeklyXp)
      .slice(0, limit)
  }

  async devicesFor(userId: string): Promise<StoredDevice[]> {
    const { data } = await this.client()
      .from('devices')
      .select('*')
      .eq('user_id', userId)
      .order('last_seen_at', { ascending: false })
    return ((data ?? []) as Record<string, unknown>[]).map(rowToDevice)
  }

  async findDevice(deviceId: string): Promise<StoredDevice | null> {
    const { data } = await this.client()
      .from('devices')
      .select('*')
      .eq('id', deviceId)
      .maybeSingle()
    return data ? rowToDevice(data) : null
  }

  async createDevice(device: StoredDevice) {
    const { error } = await this.client().from('devices').insert({
      id: device.id,
      user_id: device.userId,
      name: device.name,
      platform: device.platform,
      app_version: device.appVersion,
      created_at: device.createdAt,
      last_seen_at: device.lastSeenAt,
    })
    if (error) throw new Error(error.message)
  }

  async touchDevice(deviceId: string) {
    await this.client()
      .from('devices')
      .update({ last_seen_at: new Date().toISOString() })
      .eq('id', deviceId)
  }

  async revokeDevice(userId: string, deviceId: string): Promise<boolean> {
    const { data } = await this.client()
      .from('devices')
      .update({ revoked_at: new Date().toISOString() })
      .eq('id', deviceId)
      // Ownership in the predicate, so a device id from elsewhere matches
      // nothing rather than being checked after the fact.
      .eq('user_id', userId)
      .is('revoked_at', null)
      .select('id')
    return ((data ?? []) as unknown[]).length > 0
  }

  async createPairing(pairing: StoredPairing) {
    const client = this.client()
    await client.from('device_pairings').delete().lt('expires_at', new Date().toISOString())
    const { error } = await client.from('device_pairings').insert({
      device_code_hash: pairing.deviceCodeHash,
      user_code: pairing.userCode,
      name: pairing.name,
      platform: pairing.platform,
      app_version: pairing.appVersion,
      created_at: pairing.createdAt,
      expires_at: pairing.expiresAt,
    })
    if (error) throw new Error(error.message)
  }

  async findPairingByUserCode(userCode: string): Promise<StoredPairing | null> {
    const { data } = await this.client()
      .from('device_pairings')
      .select('*')
      .eq('user_code', userCode)
      .gte('expires_at', new Date().toISOString())
      .maybeSingle()
    return data ? rowToPairing(data) : null
  }

  async findPairingByCodeHash(hash: string): Promise<StoredPairing | null> {
    const { data } = await this.client()
      .from('device_pairings')
      .select('*')
      .eq('device_code_hash', hash)
      .gte('expires_at', new Date().toISOString())
      .maybeSingle()
    return data ? rowToPairing(data) : null
  }

  async approvePairing(userCode: string, userId: string): Promise<boolean> {
    const { data } = await this.client()
      .from('device_pairings')
      .update({ user_id: userId, approved_at: new Date().toISOString() })
      .eq('user_code', userCode)
      .gte('expires_at', new Date().toISOString())
      .is('approved_at', null)
      .select('user_code')
    return ((data ?? []) as unknown[]).length > 0
  }

  async deletePairing(hash: string) {
    await this.client().from('device_pairings').delete().eq('device_code_hash', hash)
  }
}

function rowToDevice(row: Record<string, unknown>): StoredDevice {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    name: row.name as string,
    platform: row.platform as string,
    appVersion: row.app_version as string,
    createdAt: row.created_at as string,
    lastSeenAt: row.last_seen_at as string,
    revokedAt: (row.revoked_at as string) ?? undefined,
  }
}

function rowToPairing(row: Record<string, unknown>): StoredPairing {
  return {
    deviceCodeHash: row.device_code_hash as string,
    userCode: row.user_code as string,
    name: row.name as string,
    platform: row.platform as string,
    appVersion: row.app_version as string,
    createdAt: row.created_at as string,
    expiresAt: row.expires_at as string,
    userId: (row.user_id as string) ?? undefined,
    approvedAt: (row.approved_at as string) ?? undefined,
  }
}

function rowToUser(row: Record<string, unknown>): StoredUser {
  return {
    id: row.id as string,
    email: row.email as string,
    displayName: row.display_name as string,
    createdAt: row.created_at as string,
    passwordHash: row.password_hash as string,
    passwordSalt: row.password_salt as string,
    plan: (row.plan as StoredUser['plan']) ?? 'free',
  }
}

let instance: Store | null = null

export function store(): Store {
  instance ??= hasSupabase() ? new SupabaseStore() : new LocalStore()
  return instance
}

/** Stable id for a local user, so re-registering the same email is rejected. */
export function userId(email: string): string {
  return createHash('sha256').update(email.toLowerCase()).digest('hex').slice(0, 32)
}
