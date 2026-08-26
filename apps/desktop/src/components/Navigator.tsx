import { useEffect, useState } from 'react'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { LessonSidebar, cn } from '@atlas/ui'
import { courses, findLessonRefById, modulesOf, type LessonRef } from '../lib/content'

export interface NavigatorProps {
  activeRef: LessonRef
  isComplete: (lessonId: string) => boolean
  onSelectLesson: (ref: LessonRef) => void
  onCollapse: () => void
}

/**
 * Left rail: pick a module, then a lesson inside it.
 *
 * The module being browsed is tracked separately from the lesson being
 * practised, so glancing at what module 6 covers does not throw away the
 * editor buffer — nothing changes until a lesson is clicked.
 */
export function Navigator({ activeRef, isComplete, onSelectLesson, onCollapse }: NavigatorProps) {
  // Keyed on module id, not slug: slugs only have to be unique inside a course,
  // so two courses may both have a `foundations`.
  const [browsingId, setBrowsingId] = useState(activeRef.module.id)

  // Following a prev/next jump into another module should move the rail with it.
  useEffect(() => {
    setBrowsingId(activeRef.module.id)
  }, [activeRef.module.id])

  const everyModule = courses.flatMap((course) =>
    modulesOf(course).map((module) => ({ course, module })),
  )
  const browsing = everyModule.find((entry) => entry.module.id === browsingId)?.module ??
    activeRef.module

  return (
    <div className="flex h-full min-h-0 w-full flex-col border-r border-rule bg-paper-raised">
      <div className="flex items-center gap-2 border-b border-rule px-3 py-2">
        <label htmlFor="module-picker" className="sr-only">
          Module
        </label>
        <select
          id="module-picker"
          value={browsing.id}
          onChange={(event) => setBrowsingId(event.target.value)}
          className={cn(
            'min-h-9 min-w-0 flex-1 rounded-field border border-rule bg-paper-sunken px-2',
            'text-caption text-ink outline-none',
            'focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40',
          )}
        >
          {courses.map((course) => (
            <optgroup key={course.id} label={course.name}>
              {modulesOf(course).map((module) => (
                <option key={module.id} value={module.id}>
                  {String(module.order).padStart(2, '0')} — {module.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <button
          type="button"
          onClick={onCollapse}
          title="Collapse the navigator"
          aria-label="Collapse the navigator"
          className={cn(
            'inline-flex size-9 shrink-0 items-center justify-center rounded-field',
            'text-muted transition-colors duration-200 ease-paper hover:bg-paper-sunken hover:text-ink',
          )}
        >
          <PanelLeftClose aria-hidden className="size-4" />
        </button>
      </div>

      <LessonSidebar
        module={browsing}
        activeLessonId={activeRef.lesson.id}
        isComplete={isComplete}
        onSelect={(lessonId) => {
          const ref = findLessonRefById(lessonId)
          if (ref) onSelectLesson(ref)
        }}
        className="min-h-0 flex-1"
      />
    </div>
  )
}

export interface NavigatorRailProps {
  onExpand: () => void
  moduleTitle: string
}

/** What the navigator collapses down to: a slim strip that can restore it. */
export function NavigatorRail({ onExpand, moduleTitle }: NavigatorRailProps) {
  return (
    <div className="flex h-full w-10 shrink-0 flex-col items-center gap-3 border-r border-rule bg-paper-raised py-2">
      <button
        type="button"
        onClick={onExpand}
        title="Show the navigator"
        aria-label="Show the navigator"
        className={cn(
          'inline-flex size-9 items-center justify-center rounded-field',
          'text-muted transition-colors duration-200 ease-paper hover:bg-paper-sunken hover:text-ink',
        )}
      >
        <PanelLeftOpen aria-hidden className="size-4" />
      </button>
      <span
        className="text-[0.6875rem] font-medium tracking-[0.08em] whitespace-nowrap text-muted uppercase"
        style={{ writingMode: 'vertical-rl' }}
      >
        {moduleTitle}
      </span>
    </div>
  )
}
