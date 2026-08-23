import 'server-only'

import { createHash, randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
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

  recordAttempt(userId: string, attempt: NewAttempt): Promise<void>
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
  activity: Record<string, ActivityDay[]>
}

const EMPTY: LocalData = {
  users: {},
  lessonProgress: {},
  moduleProgress: {},
  exerciseState: {},
  attempts: {},
  activity: {},
}

const DATA_DIR = path.join(process.cwd(), '.data')
const DATA_FILE = path.join(DATA_DIR, 'store.json')

class LocalStore implements Store {
  private cache: LocalData | null = null
  /** Serializes writes so two concurrent requests cannot clobber each other. */
  private queue: Promise<unknown> = Promise.resolve()

  private async read(): Promise<LocalData> {
    if (this.cache) return this.cache

    let loaded: LocalData
    try {
      loaded = { ...EMPTY, ...JSON.parse(await readFile(DATA_FILE, 'utf8')) }
    } catch {
      // No file yet, or it was corrupted. Either way, start clean rather than
      // taking the whole server down on a first run.
      loaded = structuredClone(EMPTY)
    }

    this.cache = loaded
    return loaded
  }

  private write<T>(mutate: (data: LocalData) => T): Promise<T> {
    const next = this.queue.then(async () => {
      const data = await this.read()
      const result = mutate(data)
      await mkdir(DATA_DIR, { recursive: true })
      await writeFile(DATA_FILE, JSON.stringify(data, null, 2))
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

  async recordAttempt(userId: string, attempt: NewAttempt) {
    await this.write((data) => {
      const rows = (data.attempts[userId] ??= [])
      rows.push({ ...attempt, id: randomUUID(), createdAt: new Date().toISOString() })
      // An unbounded append-only log in a JSON file is a memory leak with extra
      // steps. Supabase keeps the full history.
      if (rows.length > 500) rows.splice(0, rows.length - 500)
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

  async recordAttempt(userId: string, attempt: NewAttempt) {
    await this.client().from('exercise_attempts').insert({
      user_id: userId,
      exercise_id: attempt.exerciseId,
      passed: attempt.passed,
      tests_passed: attempt.testsPassed,
      tests_total: attempt.testsTotal,
      duration_ms: attempt.durationMs,
      stdout_tail: attempt.stdoutTail?.slice(-4000),
    })
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
