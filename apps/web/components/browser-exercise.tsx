'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { type Levelled, LevelUpMoment, useLevelUp } from './level-up-moment'

interface Verdict {
  passed: boolean
  testsPassed: number
  testsTotal: number
  durationMs: number
  stdoutTail: string
}

/**
 * Practice, in the page.
 *
 * The premise this product was built on asks for real code in the browser and
 * locally, and only the second half shipped: a reader who wanted to try one
 * exercise had to install a desktop app first. This is the other half. It runs
 * the same tests against the same course library in the same interpreter, and
 * posts the result to the same route, so an attempt made here is worth exactly
 * what an attempt made there is worth.
 *
 * It is not the desktop app and does not try to be. There is no terminal, no
 * file tree and no project mode. It is one buffer and a Run button, which is the
 * whole of what somebody deciding whether to bother needs.
 */
export function BrowserExercise({
  exerciseId,
  scaffold,
  files,
}: {
  exerciseId: string
  scaffold: string
  /** Everything the exercise ships: the course library, `test.py`, the rest. */
  files: Record<string, string>
}) {
  const [code, setCode] = useState(scaffold)
  const [state, setState] = useState<'idle' | 'booting' | 'running'>('idle')
  const [verdict, setVerdict] = useState<Verdict | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [booted, setBooted] = useState(false)
  const level = useLevelUp()

  const worker = useRef<Worker | null>(null)
  const pending = useRef(0)

  // Torn down on unmount so navigating away does not leave an interpreter and
  // its 13 MB of heap alive behind the next page.
  useEffect(() => () => worker.current?.terminate(), [])

  const run = useCallback(() => {
    setError(null)
    setVerdict(null)
    setState(booted ? 'running' : 'booting')

    if (!worker.current) worker.current = new Worker('/grader.js', { type: 'module' })
    const id = ++pending.current

    worker.current.onmessage = async (event: MessageEvent) => {
      // A verdict from a run the student has already superseded. Dropping it
      // stops a slow first run overwriting a fast second one.
      if (event.data.id !== pending.current) return

      setState('idle')
      setBooted(true)

      if (!event.data.ok) {
        setError(event.data.message || 'The runtime could not start.')
        return
      }

      const result: Verdict = event.data
      setVerdict(result)

      // Recorded server-side like any other attempt. The route derives the user
      // from the session and looks the exercise up in the manifest, so nothing
      // here decides what it was worth. A signed-out reader gets a 401 and their
      // practice simply is not recorded, which is the correct outcome and not an
      // error worth showing them.
      try {
        const response = await fetch('/api/attempts', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            exerciseId,
            passed: result.passed,
            testsPassed: result.testsPassed,
            testsTotal: result.testsTotal,
            durationMs: result.durationMs,
            stdoutTail: result.stdoutTail,
          }),
        })
        if (response.ok) {
          const body = (await response.json().catch(() => ({}))) as Levelled
          if (body.levelledTo) level.setLevelledTo(body.levelledTo)
        }
      } catch {
        // Offline. They still got their verdict, which is the part that matters.
      }
    }

    worker.current.postMessage({ id, files, solution: code })
  }, [booted, code, exerciseId, files, level])

  const busy = state !== 'idle'

  return (
    <div className="mt-7">
      <label htmlFor="solution" className="text-eyebrow font-medium uppercase text-muted">
        solution.py
      </label>

      <textarea
        id="solution"
        value={code}
        onChange={(event) => setCode(event.target.value)}
        onKeyDown={(event) => {
          // A Python buffer that cannot indent is not a Python buffer.
          if (event.key !== 'Tab') return
          event.preventDefault()
          const target = event.currentTarget
          const { selectionStart: start, selectionEnd: end } = target
          setCode(code.slice(0, start) + '    ' + code.slice(end))
          requestAnimationFrame(() => target.setSelectionRange(start + 4, start + 4))
        }}
        spellCheck={false}
        rows={18}
        className="mt-3 w-full resize-y rounded-sheet border border-rule bg-paper-raised p-4 font-mono text-[13px] leading-relaxed text-ink focus:border-accent focus:outline-none"
      />

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="inline-flex min-h-11 items-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60"
        >
          {state === 'booting' ? 'Starting Python' : state === 'running' ? 'Running' : 'Run tests'}
        </button>

        <button
          type="button"
          onClick={() => {
            setCode(scaffold)
            setVerdict(null)
            setError(null)
          }}
          disabled={busy}
          className="min-h-11 text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink disabled:opacity-60"
        >
          Reset
        </button>

        {state === 'booting' && (
          <span className="text-caption text-muted">
            first run downloads Python, about 13 MB, once
          </span>
        )}

        {verdict && (
          <span
            role="status"
            className={`font-mono text-caption tabular-nums ${verdict.passed ? 'text-pass' : 'text-fail'}`}
          >
            {verdict.testsPassed}/{verdict.testsTotal} passed
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-caption text-fail">
          {error} You can still do this exercise in the desktop app.
        </p>
      )}

      {verdict && !verdict.passed && (
        <pre className="mt-4 max-h-80 overflow-auto rounded-sheet border border-rule bg-paper-raised p-4 text-[13px] leading-relaxed">
          <code>{verdict.stdoutTail}</code>
        </pre>
      )}

      <LevelUpMoment levelledTo={level.levelledTo} onDone={level.clear} />
    </div>
  )
}
