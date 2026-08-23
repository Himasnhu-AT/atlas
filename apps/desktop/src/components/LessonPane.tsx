import { useEffect, useRef, useState } from 'react'

import { findLessonRefById, formatDuration, type LessonRef } from '../lib/content'
import { loadLesson } from '../lib/lessons'

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

  const [html, setHtml] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setHtml(null)
    setError(null)
    scrollRef.current?.scrollTo({ top: 0 })

    void (async () => {
      try {
        const compiled = await loadLesson(lesson.id)
        if (cancelled) return

        if (!compiled) {
          setError(
            'This lesson is not in the current build. Run ' +
              '`pnpm content` and start the app again.',
          )
          return
        }
        setHtml(compiled.html)
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
      <article className="mx-auto w-full max-w-[68ch] px-8 py-9">
        <header className="max-w-[58ch]">
          <p className="text-eyebrow font-medium tracking-[0.16em] text-muted uppercase">
            {module.name}
          </p>

          <h1 className="mt-4 font-serif text-[1.75rem] leading-[1.15] tracking-[-0.015em] text-ink">
            {lesson.title}
          </h1>

          <p className="mt-4 font-serif text-lead text-ink-soft">{lesson.summary}</p>

          <p className="mt-4 text-caption text-muted">
            Lesson {position} of {module.lessons.length} · {formatDuration(lesson.estimatedMinutes)}
            {done && ' · completed'}
          </p>
        </header>

        <hr className="mt-9 mb-10 border-rule" />

        {error ? (
          <p className="rounded-lg border border-fail/30 bg-fail/5 px-4 py-3 text-sm text-fail">
            {error}
          </p>
        ) : html === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          // The content build produced this HTML from markdown in this repo,
          // with highlighting already applied. It is our own build output, not
          // anything a user supplied.
          // The click handler only intercepts anchors the build marked with
          // `data-lesson`; everything else in the body behaves normally.
          <div
            className="prose-learn"
            onClick={handleBodyClick}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
      </article>
    </div>
  )
}
