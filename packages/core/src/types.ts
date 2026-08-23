import { z } from 'zod'

/**
 * The domain model shared by the web app, the desktop app, and the API between
 * them. Content types live in @atlas/learning; these describe users and their
 * progress through it.
 */

export const ProgressStatus = z.enum(['not_started', 'in_progress', 'completed'])
export type ProgressStatus = z.infer<typeof ProgressStatus>

export const ModuleStatus = z.enum(['locked', 'available', 'in_progress', 'completed'])
export type ModuleStatus = z.infer<typeof ModuleStatus>

export const User = z.object({
  id: z.string(),
  email: z.email(),
  displayName: z.string().min(1).max(80),
  avatarUrl: z.url().optional(),
  createdAt: z.iso.datetime(),
})
export type User = z.infer<typeof User>

/**
 * A module as the registry knows it. Deliberately metadata only: bodies ship
 * inside the apps, and the registry exists so the server can decide what is
 * live, at what version, and what unlocks what.
 */
export const ModuleRecord = z.object({
  id: z.string(),
  courseId: z.string(),
  slug: z.string(),
  name: z.string(),
  version: z.string(),
  isActive: z.boolean(),
  prerequisites: z.array(z.string()),
  /**
   * A grouping inside one course, and deliberately a plain string.
   *
   * It used to be `base | cli | agent | frameworks | projects`, which are words
   * that only mean anything to the AI course. Each course declares its own
   * tracks in its `course.yaml`, the content build checks a module against its
   * own course's list, and the registry only stores what the build already
   * validated.
   */
  track: z.string().min(1),
  order: z.number().int().nonnegative(),
  difficulty: z.enum(['beginner', 'intermediate', 'advanced']),
  estimatedHours: z.number().positive(),
})
export type ModuleRecord = z.infer<typeof ModuleRecord>

/** A course as the registry knows it. Metadata only, like `ModuleRecord`. */
export const CourseRecord = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  version: z.string(),
  isActive: z.boolean(),
  order: z.number().int().nonnegative(),
})
export type CourseRecord = z.infer<typeof CourseRecord>

export const LessonProgress = z.object({
  lessonId: z.string(),
  moduleId: z.string(),
  status: ProgressStatus,
  secondsSpent: z.number().int().nonnegative(),
  startedAt: z.iso.datetime().optional(),
  completedAt: z.iso.datetime().optional(),
})
export type LessonProgress = z.infer<typeof LessonProgress>

export const ModuleProgress = z.object({
  moduleId: z.string(),
  status: ModuleStatus,
  lessonsCompleted: z.number().int().nonnegative(),
  lessonsTotal: z.number().int().nonnegative(),
  startedAt: z.iso.datetime().optional(),
  completedAt: z.iso.datetime().optional(),
})
export type ModuleProgress = z.infer<typeof ModuleProgress>

/**
 * The student's working buffer for one exercise, synced so they can close the
 * app and pick up where they left off.
 */
export const ExerciseState = z.object({
  exerciseId: z.string(),
  currentCode: z.string(),
  peekedReferenceAt: z.iso.datetime().optional(),
  updatedAt: z.iso.datetime(),
})
export type ExerciseState = z.infer<typeof ExerciseState>

/** One test run. Append only: the history is the interesting part. */
export const ExerciseAttempt = z.object({
  id: z.string(),
  exerciseId: z.string(),
  passed: z.boolean(),
  testsPassed: z.number().int().nonnegative(),
  testsTotal: z.number().int().nonnegative(),
  durationMs: z.number().int().nonnegative(),
  createdAt: z.iso.datetime(),
})
export type ExerciseAttempt = z.infer<typeof ExerciseAttempt>

export const NewAttempt = ExerciseAttempt.omit({ id: true, createdAt: true }).extend({
  /** Tail of the runner output, truncated server-side. Never the whole log. */
  stdoutTail: z.string().max(4000).optional(),
})
export type NewAttempt = z.infer<typeof NewAttempt>

export const Device = z.object({
  id: z.string(),
  name: z.string(),
  platform: z.string(),
  appVersion: z.string(),
  lastSeenAt: z.iso.datetime(),
})
export type Device = z.infer<typeof Device>

export const ActivityDay = z.object({
  day: z.string(),
  lessonsTouched: z.number().int().nonnegative(),
  attempts: z.number().int().nonnegative(),
})
export type ActivityDay = z.infer<typeof ActivityDay>

/** Everything the dashboard needs, in one request. */
export const ProgressSnapshot = z.object({
  modules: z.array(ModuleProgress),
  lessons: z.array(LessonProgress),
  activity: z.array(ActivityDay),
  streakDays: z.number().int().nonnegative(),
})
export type ProgressSnapshot = z.infer<typeof ProgressSnapshot>

/** Request bodies. Note that none of them carry a user id: see below. */

export const UpdateLessonProgress = z.object({
  lessonId: z.string(),
  moduleId: z.string(),
  status: ProgressStatus,
  secondsSpent: z.number().int().nonnegative().max(86_400).optional(),
})
export type UpdateLessonProgress = z.infer<typeof UpdateLessonProgress>

export const SaveExerciseCode = z.object({
  exerciseId: z.string(),
  currentCode: z.string().max(200_000),
  peeked: z.boolean().optional(),
})
export type SaveExerciseCode = z.infer<typeof SaveExerciseCode>

export const Credentials = z.object({
  email: z.email(),
  password: z.string().min(8).max(200),
})
export type Credentials = z.infer<typeof Credentials>

export const SignupRequest = Credentials.extend({
  displayName: z.string().min(1).max(80),
})
export type SignupRequest = z.infer<typeof SignupRequest>

/**
 * No request schema carries a user id. The server derives it from the session
 * on every route, and a user id arriving in a body is ignored rather than
 * trusted. That single rule is what stands in for row level security here,
 * since the client never talks to the database directly.
 */

export const ApiError = z.object({
  error: z.string(),
  detail: z.string().optional(),
})
export type ApiError = z.infer<typeof ApiError>
