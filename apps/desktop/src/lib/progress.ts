import { useCallback, useEffect, useMemo, useState } from 'react'

import { syncQueue } from './ipc'

/** What the grader reports, as the API's `NewAttempt` wants it. */
export interface AttemptReport {
  passed: boolean
  testsPassed: number
  testsTotal: number
  durationMs: number
  stdoutTail?: string
}

/**
 * Progress tracking for the desktop app.
 *
 * Local first, always. The app is offline-capable by design, so completion is
 * written to localStorage immediately and works with no account.
 *
 * Every event is also queued to a Rust-owned outbox, whether or not anyone is
 * signed in. That is the change from the fire-and-forget `fetch` this replaces,
 * which needed a live server and a session at the moment of the event and
 * silently dropped everything otherwise. It also had never worked in
 * development at all: the Tauri CSP allowed the Vite port and not the API's, so
 * every request was blocked and the bare `catch {}` ate the violation.
 *
 * Queueing unconditionally means somebody who practises offline for three weeks
 * and then makes an account is credited for all of it, because the backlog is
 * still there when they pair.
 */

const STORAGE_KEY = 'atlas.progress.v1'

interface LocalProgress {
  completed: Record<string, string>
  /**
   * `count` is how many times this exercise has been run, and it is optional
   * on purpose. The reader spreads over EMPTY, so a record written before this
   * field existed reads back with it absent rather than throwing, and bumping
   * the storage key to add a counter would have discarded everybody's
   * completions.
   */
  attempts: Record<string, { passed: boolean; at: string; count?: number }>
  /** When the learner revealed the reference, by exercise id. Sticky. */
  peeked: Record<string, string>
}

const EMPTY: LocalProgress = { completed: {}, attempts: {}, peeked: {} }

function read(): LocalProgress {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return EMPTY
    return { ...EMPTY, ...JSON.parse(raw) }
  } catch {
    return EMPTY
  }
}

function write(value: LocalProgress): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {
    // Storage full or blocked. The in-memory state still works for this session.
  }
}

/**
 * Hand an event to the outbox.
 *
 * Never throws into the caller. Failing to queue must not undo work the learner
 * actually did, and the local state is authoritative for what they have
 * finished either way.
 */
function queue(kind: string, payload: unknown): void {
  void syncQueue(kind, payload).catch((error) => {
    console.warn('[desktop] could not queue an event for sync', error)
  })
}

export function useProgress() {
  const [state, setState] = useState<LocalProgress>(EMPTY)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setState(read())
    setLoading(false)
  }, [])

  const isComplete = useCallback(
    (lessonId: string) => Boolean(state.completed[lessonId]),
    [state.completed],
  )

  const markComplete = useCallback(
    (lessonId: string, moduleId: string, complete = true) => {
      setState((previous) => {
        const completed = { ...previous.completed }
        if (complete) completed[lessonId] = new Date().toISOString()
        else delete completed[lessonId]

        const next = { ...previous, completed }
        write(next)
        return next
      })

      queue('lesson.progress', {
        lessonId,
        moduleId,
        status: complete ? 'completed' : 'in_progress',
      })
    },
    [],
  )

  /**
   * The learner asked for the reference.
   *
   * This is deliberately recorded, and deliberately sticky: revealing the answer
   * is a real event in the pedagogy, and the server already has a
   * `peeked_reference_at` column that only the web app ever wrote. Nothing here
   * set it, so a "solved it unaided" signal read from the server would have been
   * true of every desktop learner regardless of what they did.
   */
  const recordPeek = useCallback((exerciseId: string, currentCode: string) => {
    setState((previous) => {
      if (previous.peeked[exerciseId]) return previous
      const next = {
        ...previous,
        peeked: { ...previous.peeked, [exerciseId]: new Date().toISOString() },
      }
      write(next)
      return next
    })

    queue('exercise.peeked', { exerciseId, currentCode, peeked: true })
  }, [])

  const hasPeeked = useCallback(
    (exerciseId: string) => Boolean(state.peeked[exerciseId]),
    [state.peeked],
  )

  /**
   * A graded run.
   *
   * This is the event the whole outbox exists for: grading happens here and
   * nowhere else, so if this does not reach the server then two thirds of the
   * economy never does. It used to be recorded locally and nothing more.
   */
  const recordAttempt = useCallback(
    (exerciseId: string, report: AttemptReport) => {
      setState((previous) => {
        const next = {
          ...previous,
          attempts: {
            ...previous.attempts,
            [exerciseId]: {
              passed: report.passed,
              at: new Date().toISOString(),
              count: (previous.attempts[exerciseId]?.count ?? 0) + 1,
            },
          },
        }
        write(next)
        return next
      })

      queue('attempt.recorded', {
        exerciseId,
        passed: report.passed,
        testsPassed: report.testsPassed,
        testsTotal: report.testsTotal,
        durationMs: report.durationMs,
        stdoutTail: report.stdoutTail?.slice(-4000),
      })
    },
    [],
  )

  const lastAttempt = useCallback(
    (exerciseId: string) => state.attempts[exerciseId],
    [state.attempts],
  )

  const completedCount = useMemo(
    () => Object.keys(state.completed).length,
    [state.completed],
  )

  return {
    loading,
    isComplete,
    markComplete,
    recordAttempt,
    recordPeek,
    hasPeeked,
    lastAttempt,
    completedCount,
  }
}
