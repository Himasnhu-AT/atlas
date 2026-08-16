import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { isDesktop } from '@learn/core'

import { AppHeader } from '../components/AppHeader'
import { BrowserBanner } from '../components/BrowserBanner'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EditorSlot } from '../components/EditorSlot'
import { ExerciseMovedBanner } from '../components/ExerciseMovedBanner'
import { LessonPane } from '../components/LessonPane'
import { Navigator, NavigatorRail } from '../components/Navigator'
import { SplitPane } from '../components/SplitPane'
import { StatusBar, type StatusMessage } from '../components/StatusBar'
import { TerminalSlot } from '../components/TerminalSlot'
import { Toolbar } from '../components/Toolbar'
import {
  findLessonRef,
  neighboursOf,
  practicePath,
  SOLUTION_FILE,
  type LessonRef,
} from '../lib/content'
import {
  checkExercise,
  prepareExercise,
  saveSolution,
  summarize,
  type ExerciseState,
  type PreparedExercise,
} from '../lib/exercise'
import { errorMessage } from '../lib/errors'
import { useLayout } from '../lib/layout'
import { rememberLesson } from '../lib/recent'
import { preflight, type PreflightReport, type TestReport } from '../lib/ipc'
import { useProgress } from '../lib/progress'

/** Router glue: resolve the URL to a lesson, then hand off to the IDE. */
export default function Practice() {
  const { moduleSlug, lessonSlug } = useParams()
  const lessonRef = findLessonRef(moduleSlug, lessonSlug)

  if (!lessonRef) return <Navigate to="/" replace />
  return <PracticeView lessonRef={lessonRef} />
}

type PendingConfirm = 'reset' | 'solution' | null

/** How long the buffer sits idle before it is written to disk. */
const AUTOSAVE_MS = 800

/**
 * What the status bar says about what was found on disk.
 *
 * `unknown` is deliberately not phrased as reassurance. The workspace predates
 * the stamp that would answer the question, so saying the work was restored
 * would be claiming something this app cannot check.
 */
const OPENED_MESSAGE: Record<ExerciseState, string> = {
  fresh: `Started ${SOLUTION_FILE} from the scaffold.`,
  restored: 'Restored your work from last time.',
  changed: 'Restored your work. This exercise has changed since you last opened it.',
  unknown: 'Restored your work from last time, from before this app tracked exercise versions.',
}

/**
 * The three-pane practice IDE.
 *
 * Mounted once for the whole session and re-pointed at a new lesson through
 * props. Remounting would tear down the pty session and throw away the
 * learner's terminal scrollback every time they moved between lessons.
 */
function PracticeView({ lessonRef }: { lessonRef: LessonRef }) {
  const { module, lesson } = lessonRef
  const navigate = useNavigate()
  const desktop = isDesktop()

  const { isComplete, markComplete, recordAttempt } = useProgress()
  const { layout, setFraction, toggleNav, toggleTerminal, reset: resetLayout } = useLayout()

  const [prepared, setPrepared] = useState<PreparedExercise | null>(null)
  const [code, setCode] = useState('')
  const [ptySessionId, setPtySessionId] = useState<string | null>(null)
  const [environment, setEnvironment] = useState<PreflightReport | null>(null)
  const [status, setStatus] = useState<StatusMessage | null>(null)
  const [running, setRunning] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null)
  const [exerciseMoved, setExerciseMoved] = useState(false)

  const done = isComplete(lesson.id)
  const { previous, next } = neighboursOf(lessonRef)
  const hasExercise = Boolean(lesson.exercise)

  /* ------------------------------------------------------------- preflight */

  // Once per session, not per lesson: spawning python3 --version on every
  // navigation would be pure overhead.
  useEffect(() => {
    if (!desktop) return
    let cancelled = false

    void preflight()
      .then((report) => {
        if (cancelled) return
        setEnvironment(report)
        if (!report.canRunExercises) {
          const problem = report.checks.find((check) => !check.ok)
          setStatus({ tone: 'error', text: problem?.remedy ?? 'Setup check failed.' })
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) setStatus({ tone: 'error', text: errorMessage(cause) })
      })

    return () => {
      cancelled = true
    }
  }, [desktop])

  /* --------------------------------------------------------- exercise load */

  useEffect(() => {
    rememberLesson(lessonRef)

    if (!desktop || !hasExercise) {
      setPrepared(null)
      setCode('')
      setExerciseMoved(false)
      return
    }

    let cancelled = false
    setPrepared(null)
    setCode('')
    setExerciseMoved(false)

    void (async () => {
      try {
        const ready = await prepareExercise(lessonRef)
        if (cancelled) return

        setPrepared(ready)
        setCode(ready.code)
        // The banner carries the `changed` case, because a line in the status
        // bar is the wrong weight for the one message that stops a learner
        // debugging code that was correct yesterday.
        setExerciseMoved(ready.state === 'changed')
        setStatus({ tone: 'info', text: OPENED_MESSAGE[ready.state] })
      } catch (cause) {
        if (!cancelled) setStatus({ tone: 'error', text: errorMessage(cause) })
      }
    })()

    return () => {
      cancelled = true
    }
    // lessonRef is derived from these two, and depending on the object itself
    // would re-run this on every render.
  }, [lesson.id, desktop, hasExercise, lessonRef])

  /* --------------------------------------------------------------- autosave */

  const savedRef = useRef('')
  useEffect(() => {
    if (!prepared || code === savedRef.current) return

    const timer = setTimeout(() => {
      savedRef.current = code
      void saveSolution(prepared.dir, code).catch((cause: unknown) => {
        setStatus({ tone: 'error', text: `Could not save: ${errorMessage(cause)}` })
      })
    }, AUTOSAVE_MS)

    return () => clearTimeout(timer)
  }, [code, prepared])

  // Flush on unmount so closing the app mid-edit does not lose the last keystrokes.
  useEffect(() => {
    return () => {
      if (prepared && savedRef.current !== code) {
        void saveSolution(prepared.dir, code)
      }
    }
  }, [prepared, code])

  /* -------------------------------------------------------------- run tests */

  const handleRun = useCallback(async () => {
    if (!prepared || running) return

    setRunning(true)
    setStatus({ tone: 'busy', text: 'Running tests…' })

    try {
      const report: TestReport = await checkExercise(prepared, code)
      savedRef.current = code

      if (report.runnerError) {
        setStatus({ tone: 'error', text: report.runnerError })
        return
      }

      recordAttempt(lesson.exercise?.id ?? lesson.id, report.passed)
      setStatus({
        tone: report.passed ? 'success' : 'error',
        text: summarize(report),
      })
    } catch (cause) {
      setStatus({ tone: 'error', text: errorMessage(cause) })
    } finally {
      setRunning(false)
    }
  }, [prepared, code, running, recordAttempt, lesson])

  /* --------------------------------------------------------------- actions */

  const handleReset = useCallback(() => {
    if (!prepared) return
    setCode(prepared.scaffold)
    // The banner offers this as its own action, so taking it answers the
    // question the banner asked and it should stop asking.
    setExerciseMoved(false)
    setStatus({ tone: 'info', text: 'Reset to the scaffold.' })
  }, [prepared])

  const handleShowSolution = useCallback(() => {
    if (!prepared) return
    setCode(prepared.reference)
    setStatus({ tone: 'info', text: 'Showing the reference solution.' })
  }, [prepared])

  const handleMarkComplete = useCallback(() => {
    markComplete(lesson.id, module.id, !done)
  }, [markComplete, lesson.id, module.id, done])

  const goTo = useCallback(
    (ref: LessonRef) => navigate(practicePath(ref.module.slug, ref.lesson.slug)),
    [navigate],
  )

  /* ----------------------------------------------------------------- render */

  const runDisabledReason = !desktop
    ? 'Running tests needs the desktop app.'
    : !hasExercise
      ? 'This lesson has nothing to run.'
      : environment && !environment.canRunExercises
        ? (environment.checks.find((check) => !check.ok)?.remedy ?? 'Setup check failed.')
        : !prepared
          ? 'Still loading the exercise.'
          : undefined

  return (
    <div className="flex h-screen min-h-0 flex-col bg-paper text-ink">
      <AppHeader
        moduleTitle={module.name}
        lessonTitle={lesson.title}
        terminalCollapsed={layout.terminalCollapsed}
        onShowTerminal={toggleTerminal}
        onResetLayout={resetLayout}
      />

      {!desktop && <BrowserBanner />}

      {exerciseMoved && (
        <ExerciseMovedBanner
          onUseScaffold={() => setPendingConfirm('reset')}
          onDismiss={() => setExerciseMoved(false)}
        />
      )}

      <div className="flex min-h-0 flex-1">
        {layout.navCollapsed ? (
          <NavigatorRail onExpand={toggleNav} moduleTitle={module.name} />
        ) : (
          // `shrink-0` and an explicit width, because Navigator's own root is
          // `w-full`: it expects a pane sized for it. In a bare flex row it
          // would take the whole window and leave the workbench at zero width.
          <div className="w-72 shrink-0">
            <Navigator
              activeRef={lessonRef}
              isComplete={isComplete}
              onSelectLesson={goTo}
              onCollapse={toggleNav}
            />
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <Toolbar
            canRun={runDisabledReason === undefined}
            runDisabledReason={runDisabledReason}
            running={running}
            onRun={() => void handleRun()}
            canEdit={Boolean(prepared)}
            onReset={() => setPendingConfirm('reset')}
            hasSolution={Boolean(prepared?.reference)}
            onShowSolution={() => setPendingConfirm('solution')}
            done={done}
            completing={false}
            onMarkComplete={handleMarkComplete}
            onPrevious={previous ? () => goTo(previous) : undefined}
            onNext={next ? () => goTo(next) : undefined}
          />

          <div className="min-h-0 flex-1">
            {(() => {
              // The lesson sits above the editor; lessons with nothing to run
              // give the whole column to the lesson rather than showing an
              // empty editor.
              const workbench = hasExercise ? (
                <SplitPane
                  direction="vertical"
                  label="Resize the lesson and editor panes"
                  fraction={layout.lessonFraction}
                  onFractionChange={(value) => setFraction('lessonFraction', value)}
                  first={<LessonPane lessonRef={lessonRef} done={done} />}
                  second={
                    <EditorSlot
                      language="python"
                      value={code}
                      onChange={setCode}
                      relPath={prepared ? `${prepared.dir}/${SOLUTION_FILE}` : undefined}
                      modified={Boolean(prepared) && code !== prepared?.scaffold}
                      onRun={() => void handleRun()}
                    />
                  }
                />
              ) : (
                <LessonPane lessonRef={lessonRef} done={done} />
              )

              if (layout.terminalCollapsed) return workbench

              return (
                <SplitPane
                  direction="horizontal"
                  label="Resize the workbench and terminal"
                  fraction={layout.workbenchFraction}
                  onFractionChange={(value) => setFraction('workbenchFraction', value)}
                  first={workbench}
                  second={
                    <TerminalSlot
                      available={desktop}
                      onSessionChange={setPtySessionId}
                      onError={(text) => setStatus({ tone: 'error', text })}
                      onCollapse={toggleTerminal}
                    />
                  }
                />
              )
            })()}
          </div>

          <StatusBar
            message={status}
            workspacePath={environment?.workspacePath ?? null}
            sessionReady={ptySessionId !== null}
            desktop={desktop}
            offline
          />
        </div>
      </div>

      <ConfirmDialog
        open={pendingConfirm !== null}
        title={pendingConfirm === 'reset' ? 'Reset your work?' : 'Show the reference solution?'}
        description={
          pendingConfirm === 'reset'
            ? 'Your current code is replaced by the original scaffold. This cannot be undone.'
            : 'Reading a working solution after a real attempt teaches you something. Reading one instead of attempting does not. Your current code will be replaced.'
        }
        confirmLabel={pendingConfirm === 'reset' ? 'Reset' : 'Show it'}
        onConfirm={() => {
          if (pendingConfirm === 'reset') handleReset()
          else handleShowSolution()
          setPendingConfirm(null)
        }}
        onCancel={() => setPendingConfirm(null)}
      />
    </div>
  )
}
