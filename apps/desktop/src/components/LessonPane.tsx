import { useEffect, useRef, useState } from 'react'
import { InteractiveRenderer, LessonStageController, WidgetRegistry } from '@atlas/ui'

import { findLessonRefById, formatDuration, type LessonRef } from '../lib/content'
import { type CompiledLesson, loadLesson } from '../lib/lessons'

export interface LessonPaneProps {
  lessonRef: LessonRef
  done: boolean
  /** Follow a cross-lesson link from inside the rendered body. */
  onNavigate?: (ref: LessonRef) => void
}

/** Centre-top pane: the lesson itself. */
export function LessonPane({ lessonRef, done, onNavigate }: LessonPaneProps) {
  const { module, lesson } = lessonRef
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const [compiled, setCompiled] = useState<CompiledLesson | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setCompiled(null)
    setError(null)
    scrollRef.current?.scrollTo({ top: 0 })

    void (async () => {
      try {
        const loaded = await loadLesson(lesson.id)
        if (cancelled) return

        if (!loaded) {
          setError(
            'This lesson is not in the current build. Run ' +
              '`pnpm content` and start the app again.',
          )
          return
        }
        setCompiled(loaded)
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      }
    })()

    return () => {
      cancelled = true
    }
  }, [lesson.id])

  const position = module.lessons.findIndex((candidate) => candidate.id === lesson.id) + 1

  /**
   * Cross-lesson links, which the content build emits as
   * `<a href="/learn/..." data-lesson="<id>">`.
   *
   * The `href` is the web app's path and is the right thing to ship in the HTML,
   * but following it here would navigate the Tauri webview out of the app and
   * into a page that does not exist inside the bundle. So the click is caught,
   * the id is resolved against the bundled catalogue, and the app routes itself.
   * A link whose target is not in this build falls through to doing nothing
   * rather than blanking the window.
   */
  function handleBodyClick(event: React.MouseEvent<HTMLDivElement>) {
    const anchor = (event.target as HTMLElement).closest?.('a[data-lesson]')
    if (!anchor) return

    event.preventDefault()
    const target = findLessonRefById(anchor.getAttribute('data-lesson') ?? '')
    if (target) onNavigate?.(target)
  }

  return (
    <div ref={scrollRef} className="h-full min-h-0 w-full overflow-y-auto bg-paper">
      {/* Set the way the site sets a lesson: eyebrow, serif title, serif lead,
          a caption of housekeeping, then a rule. The pane is narrower than a
          browser column, so the title steps down from `text-title` to a fixed
          size, but the order and the voice are the site's. */}
      <article className="mx-auto w-full max-w-[68ch] px-6 py-10 sm:px-8">
        <header className="max-w-[62ch]">
          <p className="text-eyebrow font-mono font-medium tracking-[0.16em] text-muted uppercase">
            {module.name}
          </p>

          <h1 className="mt-4 font-serif text-[clamp(1.75rem,2.8vw,2.25rem)] leading-[1.12] tracking-[-0.015em] text-balance text-ink">
            {lesson.title}
          </h1>

          <p className="mt-4 max-w-[56ch] font-serif text-lead text-ink-soft">{lesson.summary}</p>

          <p className="mt-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-caption text-muted">
            Lesson {position} of {module.lessons.length} · {formatDuration(lesson.estimatedMinutes)}
            {done && (
              <span className="font-medium text-pass">Completed</span>
            )}
          </p>
        </header>

        <hr className="mt-10 mb-8 border-rule" />

        {error ? (
          <div role="alert" className="border-l-2 border-fail bg-fail-wash px-4 py-3 text-sm text-fail-deep">
            <p>{error}</p>
          </div>
        ) : compiled === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          (() => {
            const InteractiveComponent = compiled.interactive
              ? WidgetRegistry[compiled.interactive.type]
              : null

            return (
              <LessonStageController
                hasInteractive={Boolean(InteractiveComponent)}
                hasExercise={Boolean(lesson.exercise)}
                interactiveNode={
                  InteractiveComponent ? (
                    <InteractiveComponent {...(compiled.interactive?.props || {})} />
                  ) : null
                }
                proseNode={
                  <div onClick={handleBodyClick}>
                    <InteractiveRenderer html={compiled.html} className="prose-compact" />
                  </div>
                }
                exerciseNode={
                  <div className="text-caption font-mono text-muted py-4">
                    Switch to the Practice tab in the bottom pane to edit <code className="text-ink">solution.py</code> and run tests.
                  </div>
                }
              />
            )
          })()
        )}
      </article>
    </div>
  )
}
