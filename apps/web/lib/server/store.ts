import 'server-only'

import { createHash, randomUUID } from 'node:crypto'
import path from 'node:path'

import type {
  ExerciseState,
  LessonProgress,
  ModuleProgress,
  NewAttempt,
  ProgressSnapshot,
  User,
} from '@atlas/core'
import { boardScore } from '@atlas/core'

/**
 * The module that talks to persistent storage (Firebase Firestore).
 *
 * All data persistence runs server-side via Firebase Admin SDK.
 * No client ever holds database credentials; the Next.js API is the security boundary.
 */

export interface StoredUser extends User {
  passwordHash: string
  passwordSalt: string
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
   */
  weeklyTargetChosen: boolean
  /** Longest run of weeks whose target was met. */
  bestWeeks: number
  leaderboardOptIn: boolean
  /**
   * Set by hand to take somebody off the board without touching their account.
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
   * Records one run. Returns false when `clientEventId` was already applied.
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

  // Admin capabilities
  listAllUsers(): Promise<StoredUser[]>
  adminStats(): Promise<{
    totalUsers: number
    totalXp: number
    totalAttempts: number
    totalPassed: number
    activeToday: number
  }>
  listRecentAttempts(limit: number): Promise<(NewAttempt & { id: string; userId: string; createdAt: string })[]>
  listAllDevices(): Promise<StoredDevice[]>
  adminSetLeaderboardExcluded(userId: string, excluded: boolean): Promise<void>
  adminAwardXp(userId: string, points: number, reason: string): Promise<number>
}

export function storageMode(): 'firebase' {
  return 'firebase'
}

export function ensureFirebaseAdmin() {
  const { getApps, initializeApp, cert } = require('firebase-admin/app')
  if (getApps().length) return getApps()[0]

  const fs = require('node:fs')
  const defaultSaPath = path.resolve(process.cwd(), 'service-account.json')
  const altSaPath = path.resolve(process.cwd(), 'apps/web/service-account.json')

  if (process.env.FIREBASE_SERVICE_ACCOUNT_KEY) {
    let creds: Record<string, unknown>
    try {
      creds = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY)
    } catch {
      creds = require(path.resolve(process.env.FIREBASE_SERVICE_ACCOUNT_KEY))
    }
    return initializeApp({
      credential: cert(creds),
      projectId: (creds.project_id as string) || process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
    })
  }

  if (fs.existsSync(defaultSaPath)) {
    const creds = JSON.parse(fs.readFileSync(defaultSaPath, 'utf8'))
    return initializeApp({
      credential: cert(creds),
      projectId: creds.project_id || process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
    })
  }

  if (fs.existsSync(altSaPath)) {
    const creds = JSON.parse(fs.readFileSync(altSaPath, 'utf8'))
    return initializeApp({
      credential: cert(creds),
      projectId: creds.project_id || process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
    })
  }

  if (process.env.FIREBASE_CLIENT_EMAIL && process.env.FIREBASE_PRIVATE_KEY) {
    return initializeApp({
      credential: cert({
        projectId: process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
        clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
        privateKey: process.env.FIREBASE_PRIVATE_KEY.replace(/\\n/g, '\n'),
      }),
      projectId: process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
    })
  }

  // No key anywhere. On Google Cloud the runtime's own identity (Application
  // Default Credentials) still works, so fall through there. Anywhere else this
  // app can verify a Google ID token, which needs no key, and then fails on the
  // first Firestore call: sign-in answers a bare 500. Say what is missing.
  if (process.env.VERCEL && !process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    throw new Error(
      'Firebase Admin has no credentials. Set FIREBASE_SERVICE_ACCOUNT_KEY to the service ' +
        'account JSON, or FIREBASE_CLIENT_EMAIL and FIREBASE_PRIVATE_KEY, in the Vercel ' +
        'project environment, then redeploy.',
    )
  }

  return initializeApp({
    projectId: process.env.FIREBASE_PROJECT_ID || 'synthai-learn',
  })
}

// Firebase Firestore store.

class FirebaseStore implements Store {
  private db() {
    ensureFirebaseAdmin()
    const { getFirestore } = require('firebase-admin/firestore')
    return getFirestore()
  }

  private fieldValue() {
    const { FieldValue } = require('firebase-admin/firestore')
    return FieldValue
  }

  async findUserByEmail(email: string): Promise<StoredUser | null> {
    const snap = await this.db()
      .collection('users')
      .where('email', '==', email.toLowerCase())
      .limit(1)
      .get()
    if (snap.empty) return null
    return snap.docs[0].data() as StoredUser
  }

  async findUserById(id: string): Promise<StoredUser | null> {
    const doc = await this.db().collection('users').doc(id).get()
    return doc.exists ? (doc.data() as StoredUser) : null
  }

  async createUser(user: StoredUser) {
    await this.db().collection('users').doc(user.id).set({
      ...user,
      email: user.email.toLowerCase(),
    })
  }

  async touchUser(id: string) {
    await this.db()
      .collection('users')
      .doc(id)
      .set({ lastSeenAt: new Date().toISOString() }, { merge: true })
  }

  async progressFor(userId: string): Promise<ProgressSnapshot> {
    const db = this.db()
    const [lessonsSnap, modulesSnap, activitySnap] = await Promise.all([
      db.collection('lesson_progress').where('userId', '==', userId).get(),
      db.collection('module_progress').where('userId', '==', userId).get(),
      db.collection('activity_days').where('userId', '==', userId).get(),
    ])

    return {
      lessons: lessonsSnap.docs.map((doc: any) => {
        const d = doc.data()
        return {
          lessonId: d.lessonId as string,
          moduleId: d.moduleId as string,
          status: d.status as LessonProgress['status'],
          secondsSpent: (d.secondsSpent as number) ?? 0,
          startedAt: (d.startedAt as string) ?? undefined,
          completedAt: (d.completedAt as string) ?? undefined,
        }
      }),
      modules: modulesSnap.docs.map((doc: any) => {
        const d = doc.data()
        return {
          moduleId: d.moduleId as string,
          status: d.status as ModuleProgress['status'],
          lessonsCompleted: (d.lessonsCompleted as number) ?? 0,
          lessonsTotal: (d.lessonsTotal as number) ?? 0,
          startedAt: (d.startedAt as string) ?? undefined,
          completedAt: (d.completedAt as string) ?? undefined,
        }
      }),
      activity: activitySnap.docs.map((doc: any) => {
        const d = doc.data()
        return {
          day: d.day as string,
          lessonsTouched: (d.lessonsTouched as number) ?? 0,
          attempts: (d.attempts as number) ?? 0,
        }
      }),
      streakDays: 0,
    }
  }

  async upsertLessonProgress(userId: string, progress: LessonProgress) {
    const docId = `${userId}__${progress.lessonId}`
    await this.db()
      .collection('lesson_progress')
      .doc(docId)
      .set(
        {
          userId,
          lessonId: progress.lessonId,
          moduleId: progress.moduleId,
          status: progress.status,
          secondsSpent: progress.secondsSpent,
          startedAt: progress.startedAt ?? null,
          completedAt: progress.completedAt ?? null,
        },
        { merge: true },
      )
  }

  async upsertModuleProgress(userId: string, progress: ModuleProgress) {
    const docId = `${userId}__${progress.moduleId}`
    await this.db()
      .collection('module_progress')
      .doc(docId)
      .set(
        {
          userId,
          moduleId: progress.moduleId,
          status: progress.status,
          lessonsCompleted: progress.lessonsCompleted,
          lessonsTotal: progress.lessonsTotal,
          startedAt: progress.startedAt ?? null,
          completedAt: progress.completedAt ?? null,
        },
        { merge: true },
      )
  }

  async recordActivity(userId: string, day: string, kind: 'lesson' | 'attempt') {
    const FieldValue = this.fieldValue()
    const docId = `${userId}__${day}`
    await this.db()
      .collection('activity_days')
      .doc(docId)
      .set(
        {
          userId,
          day,
          lessonsTouched: FieldValue.increment(kind === 'lesson' ? 1 : 0),
          attempts: FieldValue.increment(kind === 'attempt' ? 1 : 0),
        },
        { merge: true },
      )
  }

  async exerciseState(userId: string, exerciseId: string): Promise<ExerciseState | null> {
    const docId = `${userId}__${exerciseId}`
    const doc = await this.db().collection('exercise_state').doc(docId).get()
    if (!doc.exists) return null
    const d = doc.data()!
    return {
      exerciseId: d.exerciseId as string,
      currentCode: (d.currentCode as string) ?? '',
      peekedReferenceAt: (d.peekedReferenceAt as string) ?? undefined,
      updatedAt: d.updatedAt as string,
    }
  }

  async saveExerciseState(userId: string, state: ExerciseState) {
    const docId = `${userId}__${state.exerciseId}`
    await this.db()
      .collection('exercise_state')
      .doc(docId)
      .set(
        {
          userId,
          exerciseId: state.exerciseId,
          currentCode: state.currentCode,
          peekedReferenceAt: state.peekedReferenceAt ?? null,
          updatedAt: state.updatedAt,
        },
        { merge: true },
      )
  }

  async recordAttempt(userId: string, attempt: NewAttempt, clientEventId?: string) {
    const db = this.db()
    const now = new Date().toISOString()
    const attemptId = randomUUID()

    if (clientEventId) {
      const eventDocRef = db.collection('attempt_events').doc(`${userId}__${clientEventId}`)
      const attemptDocRef = db.collection('exercise_attempts').doc(attemptId)

      return await db.runTransaction(async (t: any) => {
        const eventDoc = await t.get(eventDocRef)
        if (eventDoc.exists) {
          return false
        }
        t.set(eventDocRef, { userId, clientEventId, createdAt: now })
        t.set(attemptDocRef, {
          id: attemptId,
          userId,
          exerciseId: attempt.exerciseId,
          passed: attempt.passed,
          testsPassed: attempt.testsPassed,
          testsTotal: attempt.testsTotal,
          durationMs: attempt.durationMs,
          stdoutTail: attempt.stdoutTail?.slice(-4000) ?? null,
          clientEventId,
          createdAt: now,
        })
        return true
      })
    }

    await db.collection('exercise_attempts').doc(attemptId).set({
      id: attemptId,
      userId,
      exerciseId: attempt.exerciseId,
      passed: attempt.passed,
      testsPassed: attempt.testsPassed,
      testsTotal: attempt.testsTotal,
      durationMs: attempt.durationMs,
      stdoutTail: attempt.stdoutTail?.slice(-4000) ?? null,
      createdAt: now,
    })
    return true
  }

  /**
   * Derived from the log rather than from counters.
   * `exercise_attempts` in Firestore is append-only and complete.
   */
  async exerciseStats(userId: string): Promise<ExerciseStats[]> {
    const snap = await this.db()
      .collection('exercise_attempts')
      .where('userId', '==', userId)
      .orderBy('createdAt', 'asc')
      .get()

    const byExercise = new Map<string, ExerciseStats>()
    for (const doc of snap.docs) {
      const row = doc.data()
      const exerciseId = row.exerciseId as string
      let stat = byExercise.get(exerciseId)
      if (!stat) {
        stat = { exerciseId, passes: 0, failures: 0, failuresBeforePass: 0 }
        byExercise.set(exerciseId, stat)
      }

      if (row.passed) {
        stat.passes += 1
        stat.firstPassedAt ??= row.createdAt as string
        const duration = (row.durationMs as number) ?? 0
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
    const doc = await this.db().collection('user_game').doc(userId).get()
    if (!doc.exists) return { ...EMPTY_GAME }
    const data = doc.data()!
    return {
      totalXp: (data.totalXp as number) ?? 0,
      weeklyTarget: (data.weeklyTarget as number) ?? EMPTY_GAME.weeklyTarget,
      weeklyTargetChosen: (data.weeklyTargetChosen as boolean) ?? false,
      bestWeeks: (data.bestWeeks as number) ?? 0,
      leaderboardOptIn: (data.leaderboardOptIn as boolean) ?? false,
      leaderboardExcluded: (data.leaderboardExcluded as boolean) ?? false,
      timezone: (data.timezone as string) ?? 'UTC',
    }
  }

  async updateGame(userId: string, patch: Partial<GameRecord>) {
    const row: Record<string, unknown> = { userId, updatedAt: new Date().toISOString() }
    if (patch.totalXp !== undefined) row.totalXp = patch.totalXp
    if (patch.weeklyTarget !== undefined) row.weeklyTarget = patch.weeklyTarget
    if (patch.weeklyTargetChosen !== undefined) row.weeklyTargetChosen = patch.weeklyTargetChosen
    if (patch.bestWeeks !== undefined) row.bestWeeks = patch.bestWeeks
    if (patch.leaderboardOptIn !== undefined) row.leaderboardOptIn = patch.leaderboardOptIn
    if (patch.leaderboardExcluded !== undefined)
      row.leaderboardExcluded = patch.leaderboardExcluded
    if (patch.timezone !== undefined) row.timezone = patch.timezone

    await this.db().collection('user_game').doc(userId).set(row, { merge: true })
  }

  async awardXp(userId: string, award: StoredAward): Promise<number> {
    const db = this.db()
    const FieldValue = this.fieldValue()
    const awardDocRef = db.collection('xp_awards').doc(`${userId}__${award.awardKey}`)
    const gameDocRef = db.collection('user_game').doc(userId)

    return await db.runTransaction(async (t: any) => {
      const awardDoc = await t.get(awardDocRef)
      if (awardDoc.exists) return 0

      t.set(awardDocRef, {
        userId,
        awardKey: award.awardKey,
        kind: award.kind,
        points: award.points,
        courseId: award.courseId ?? null,
        rulesVersion: award.rulesVersion,
        occurredAt: award.occurredAt,
        awardedAt: award.awardedAt,
      })

      t.set(
        gameDocRef,
        {
          userId,
          totalXp: FieldValue.increment(award.points),
          updatedAt: new Date().toISOString(),
        },
        { merge: true },
      )

      return award.points
    })
  }

  async awardsFor(userId: string): Promise<StoredAward[]> {
    const snap = await this.db()
      .collection('xp_awards')
      .where('userId', '==', userId)
      .orderBy('awardedAt', 'desc')
      .get()

    return snap.docs.map((doc: any) => {
      const row = doc.data()
      return {
        awardKey: row.awardKey as string,
        kind: row.kind as string,
        points: (row.points as number) ?? 0,
        courseId: (row.courseId as string) ?? undefined,
        rulesVersion: (row.rulesVersion as number) ?? 1,
        occurredAt: row.occurredAt as string,
        awardedAt: row.awardedAt as string,
      }
    })
  }

  async sealsFor(userId: string) {
    const snap = await this.db()
      .collection('user_seals')
      .where('userId', '==', userId)
      .get()

    return snap.docs.map((doc: any) => {
      const row = doc.data()
      return {
        sealId: row.sealId as string,
        earnedAt: row.earnedAt as string,
      }
    })
  }

  async grantSeal(userId: string, sealId: string, courseId?: string): Promise<boolean> {
    const db = this.db()
    const sealDocRef = db.collection('user_seals').doc(`${userId}__${sealId}`)

    return await db.runTransaction(async (t: any) => {
      const doc = await t.get(sealDocRef)
      if (doc.exists) return false
      t.set(sealDocRef, {
        userId,
        sealId,
        courseId: courseId ?? null,
        earnedAt: new Date().toISOString(),
      })
      return true
    })
  }

  async weeklyLeaderboard(since: string, limit: number): Promise<LeaderboardEntry[]> {
    const db = this.db()
    const gameSnap = await db
      .collection('user_game')
      .where('leaderboardOptIn', '==', true)
      .get()

    const optedIn = gameSnap.docs
      .map((d: any) => d.data())
      .filter((g: any) => !g.leaderboardExcluded)

    const ids = optedIn.map((r: any) => r.userId as string)
    if (ids.length === 0) return []

    const [awardsSnap, usersSnap] = await Promise.all([
      db.collection('xp_awards').where('awardedAt', '>=', since).get(),
      db.collection('users').get(),
    ])

    const names = new Map(
      usersSnap.docs.map((d: any) => {
        const u = d.data()
        return [u.id as string, u.displayName as string]
      }),
    )

    const byUserDay = new Map<string, Record<string, number>>()
    for (const doc of awardsSnap.docs) {
      const row = doc.data()
      const id = row.userId as string
      if (!ids.includes(id)) continue

      const day = String(row.awardedAt ?? '').slice(0, 10)
      const days = byUserDay.get(id) ?? {}
      days[day] = (days[day] ?? 0) + ((row.points as number) ?? 0)
      byUserDay.set(id, days)
    }

    const weekly = new Map<string, number>()
    for (const [id, days] of byUserDay) weekly.set(id, boardScore(days))

    return optedIn
      .map((r: any) => ({
        userId: r.userId as string,
        displayName: names.get(r.userId as string) ?? 'Someone',
        weeklyXp: weekly.get(r.userId as string) ?? 0,
        totalXp: (r.totalXp as number) ?? 0,
      }))
      .sort((a: any, b: any) => b.weeklyXp - a.weeklyXp)
      .slice(0, limit)
  }

  async devicesFor(userId: string): Promise<StoredDevice[]> {
    const snap = await this.db()
      .collection('devices')
      .where('userId', '==', userId)
      .get()

    return snap.docs
      .map((d: any) => d.data() as StoredDevice)
      .sort((a: any, b: any) => b.lastSeenAt.localeCompare(a.lastSeenAt))
  }

  async findDevice(deviceId: string): Promise<StoredDevice | null> {
    const doc = await this.db().collection('devices').doc(deviceId).get()
    return doc.exists ? (doc.data() as StoredDevice) : null
  }

  async createDevice(device: StoredDevice) {
    await this.db().collection('devices').doc(device.id).set(device)
  }

  async touchDevice(deviceId: string) {
    await this.db()
      .collection('devices')
      .doc(deviceId)
      .update({ lastSeenAt: new Date().toISOString() })
  }

  async revokeDevice(userId: string, deviceId: string): Promise<boolean> {
    const db = this.db()
    const docRef = db.collection('devices').doc(deviceId)

    return await db.runTransaction(async (t: any) => {
      const doc = await t.get(docRef)
      if (!doc.exists) return false
      const data = doc.data()
      if (data.userId !== userId || data.revokedAt) return false
      t.update(docRef, { revokedAt: new Date().toISOString() })
      return true
    })
  }

  async createPairing(pairing: StoredPairing) {
    const db = this.db()
    const now = new Date().toISOString()
    const expiredSnap = await db.collection('device_pairings').where('expiresAt', '<', now).get()
    const batch = db.batch()
    for (const doc of expiredSnap.docs) {
      batch.delete(doc.ref)
    }
    batch.set(db.collection('device_pairings').doc(pairing.deviceCodeHash), pairing)
    await batch.commit()
  }

  async findPairingByUserCode(userCode: string): Promise<StoredPairing | null> {
    const now = new Date().toISOString()
    const snap = await this.db()
      .collection('device_pairings')
      .where('userCode', '==', userCode)
      .limit(1)
      .get()

    if (snap.empty) return null
    const pairing = snap.docs[0].data() as StoredPairing
    return pairing.expiresAt >= now ? pairing : null
  }

  async findPairingByCodeHash(hash: string): Promise<StoredPairing | null> {
    const now = new Date().toISOString()
    const doc = await this.db().collection('device_pairings').doc(hash).get()
    if (!doc.exists) return null
    const pairing = doc.data() as StoredPairing
    return pairing.expiresAt >= now ? pairing : null
  }

  async approvePairing(userCode: string, userId: string): Promise<boolean> {
    const db = this.db()
    const now = new Date().toISOString()
    const snap = await db
      .collection('device_pairings')
      .where('userCode', '==', userCode)
      .limit(1)
      .get()

    if (snap.empty) return false
    const docRef = snap.docs[0].ref
    return await db.runTransaction(async (t: any) => {
      const doc = await t.get(docRef)
      if (!doc.exists) return false
      const data = doc.data()
      if (data.expiresAt < now || data.approvedAt) return false
      t.update(docRef, { userId, approvedAt: now })
      return true
    })
  }

  async deletePairing(hash: string) {
    await this.db().collection('device_pairings').doc(hash).delete()
  }

  async listAllUsers(): Promise<StoredUser[]> {
    const snap = await this.db().collection('users').get()
    return snap.docs
      .map((d: any) => d.data() as StoredUser)
      .sort((a: any, b: any) => (b.createdAt || '').localeCompare(a.createdAt || ''))
  }

  async adminStats() {
    const db = this.db()
    const [usersSnap, gamesSnap, attemptsSnap, activitySnap] = await Promise.all([
      db.collection('users').get(),
      db.collection('user_game').get(),
      db.collection('exercise_attempts').get(),
      db.collection('activity_days').get(),
    ])
    const totalUsers = usersSnap.size
    const totalXp = gamesSnap.docs.reduce((sum: number, d: any) => sum + (d.data().totalXp || 0), 0)
    const totalAttempts = attemptsSnap.size
    const totalPassed = attemptsSnap.docs.filter((d: any) => d.data().passed).length
    const today = new Date().toISOString().slice(0, 10)
    const activeToday = new Set(
      activitySnap.docs
        .map((d: any) => d.data())
        .filter((d: any) => d.day === today && (d.lessonsTouched > 0 || d.attempts > 0))
        .map((d: any) => d.userId),
    ).size

    return {
      totalUsers,
      totalXp,
      totalAttempts,
      totalPassed,
      activeToday,
    }
  }

  async listRecentAttempts(limit: number) {
    const snap = await this.db()
      .collection('exercise_attempts')
      .orderBy('createdAt', 'desc')
      .limit(limit)
      .get()
    return snap.docs.map(
      (d: any) => d.data() as NewAttempt & { id: string; userId: string; createdAt: string },
    )
  }

  async listAllDevices(): Promise<StoredDevice[]> {
    const snap = await this.db().collection('devices').get()
    return snap.docs
      .map((d: any) => d.data() as StoredDevice)
      .sort((a: any, b: any) => (b.lastSeenAt || '').localeCompare(a.lastSeenAt || ''))
  }

  async adminSetLeaderboardExcluded(userId: string, excluded: boolean) {
    await this.db().collection('user_game').doc(userId).set(
      { leaderboardExcluded: excluded, updatedAt: new Date().toISOString() },
      { merge: true },
    )
  }

  async adminAwardXp(userId: string, points: number, _reason: string): Promise<number> {
    const award: StoredAward = {
      awardKey: `admin:${randomUUID()}`,
      kind: 'quest',
      points,
      rulesVersion: 1,
      occurredAt: new Date().toISOString(),
      awardedAt: new Date().toISOString(),
    }
    return this.awardXp(userId, award)
  }
}

let instance: Store | null = null

export function store(): Store {
  instance ??= new FirebaseStore()
  return instance
}

/** Stable id for a local user, so re-registering the same email is rejected. */
export function userId(email: string): string {
  return createHash('sha256').update(email.toLowerCase()).digest('hex').slice(0, 32)
}
