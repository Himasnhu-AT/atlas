import type { ComponentPropsWithRef } from 'react'
import { cn } from '../lib/cn'

/**
 * Structural shapes rather than imports from a content package, so this
 * component stays usable by any caller whose data looks like this.
 */
export interface SidebarLesson {
  id: string
  slug: string
  title: string
  estimatedMinutes: number
}

export interface SidebarModule {
  slug: string
  name: string
  order: number
  lessons: SidebarLesson[]
}

export interface LessonSidebarProps
  extends Omit<ComponentPropsWithRef<'nav'>, 'children' | 'onSelect'> {
  module: SidebarModule
  /** Lesson currently on screen. */
  activeLessonId?: string | null
  isComplete: (lessonId: string) => boolean
  onSelect: (lessonId: string) => void
}

/**
 * Lesson list for a single module.
 *
 * This is the desktop half of the same contents list the site renders in the
 * margin of a lesson, and it is written to match it rather than to be an app
 * version of it: a two digit number set in mono, the title, and nothing else.
 * A reader who moves between the two should not have to learn a second
 * vocabulary for the same list.
 *
 * The desktop knows one thing the site's margin column does not, which is
 * whether a lesson has been finished on this machine. That shows as a rule
 * along the leading edge and the number changing colour. It is deliberately
 * not a filled badge: a completed lesson is a fact about the reader, not a
 * status pill, and thirty of them down the rail would read as a dashboard.
 */
export function LessonSidebar({
  module,
  activeLessonId = null,
  isComplete,
  onSelect,
  className,
  ...props
}: LessonSidebarProps) {
  const completed = module.lessons.reduce(
    (total, lesson) => (isComplete(lesson.id) ? total + 1 : total),
    0,
  )
  const total = module.lessons.length

  return (
    <nav
      aria-label={`${module.name} lessons`}
      className={cn('flex h-full min-h-0 flex-col', className)}
      {...props}
    >
      <div className="flex flex-col gap-1 px-4 pt-4 pb-3">
        <span className="text-eyebrow font-medium tracking-[0.16em] text-muted uppercase">
          Module {String(module.order).padStart(2, '0')}
        </span>
        <h2 className="font-serif text-[0.9375rem] leading-snug text-ink">{module.name}</h2>
        <p className="text-caption text-muted">
          {completed} of {total} read
        </p>
      </div>

      <ol className="min-h-0 flex-1 overflow-y-auto border-t border-rule px-2 py-2">
        {module.lessons.map((lesson, index) => {
          const done = isComplete(lesson.id)
          const active = lesson.id === activeLessonId

          return (
            <li key={lesson.id}>
              <button
                type="button"
                onClick={() => onSelect(lesson.id)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  // min-h-11 is the 44px touch target, and it also gives the
                  // row the airy line spacing a contents list wants.
                  'flex min-h-11 w-full items-baseline gap-3 border-l-2 py-2 pr-2 pl-3 text-left',
                  'text-caption transition-colors duration-200 ease-paper',
                  active
                    ? 'border-accent text-ink'
                    : done
                      ? 'border-pass/40 text-muted hover:text-ink'
                      : 'border-transparent text-muted hover:text-ink',
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    'shrink-0 font-mono tabular-nums',
                    done ? 'text-pass' : active ? 'text-accent' : 'text-muted',
                  )}
                >
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span className={cn('min-w-0', active && 'font-medium')}>
                  {lesson.title}
                  {done && <span className="sr-only"> — read</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
