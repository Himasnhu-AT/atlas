import { useCallback, useEffect, useMemo, useState } from 'react'

/**
 * Progress tracking for the desktop app.
 *
 * Local first, always. The app is offline-capable by design, so completion is
 * written to localStorage immediately and works with no account. When a server
 * is configured and the learner is signed in, the same events are mirrored to
 * the API on a best-effort basis; a failed sync never blocks or reverts the
 * local state, because losing a tick because the wifi dropped is worse than a
 * dashboard being a few minutes stale.
 */

const STORAGE_KEY = 'learn.progress.v1'

interface LocalProgress {
  completed: Record<string, string>
  attempts: Record<string, { passed: boolean; at: string }>
}

const EMPTY: LocalProgress = { completed: {}, attempts: {} }

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

/** Where the API lives. Unset means the app runs purely offline. */
function apiBase(): string | null {
  const configured = import.meta.env.VITE_API_URL
  return typeof configured === 'string' && configured.trim() !== '' ? configured : null
}

async function mirror(path: string, body: unknown): Promise<void> {
  const base = apiBase()
  if (!base) return

  try {
    await fetch(`${base}${path}`, {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    })
  } catch {
    // Offline, or not signed in. Local state is authoritative either way.
  }
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

      void mirror('/api/progress', {
        lessonId,
        moduleId,
        status: complete ? 'completed' : 'in_progress',
      })
    },
    [],
  )

  const recordAttempt = useCallback((exerciseId: string, passed: boolean) => {
    setState((previous) => {
      const next = {
        ...previous,
        attempts: { ...previous.attempts, [exerciseId]: { passed, at: new Date().toISOString() } },
      }
      write(next)
      return next
    })
  }, [])

  const lastAttempt = useCallback(
    (exerciseId: string) => state.attempts[exerciseId],
    [state.attempts],
  )

  const completedCount = useMemo(
    () => Object.keys(state.completed).length,
    [state.completed],
  )

  return { loading, isComplete, markComplete, recordAttempt, lastAttempt, completedCount }
}
