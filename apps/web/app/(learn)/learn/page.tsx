import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { activeCourses, activeModules } from '@/lib/content'

export const metadata: Metadata = {
  title: 'Courses',
  description: 'Every course on SynthAI Labs, prerequisites, and what each track asks you to build.',
}

const COURSE_REQUIREMENTS: Record<
  string,
  { prerequisites: string; recommended: string | null }
> = {
  'intro-programming': {
    prerequisites: 'None',
    recommended: 'Start here if new to low-level memory, systems programming, or C/C++',
  },
  'ai-agents': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming (Modules 00–04)',
  },
  'data-engineering': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming (Modules 00–01)',
  },
  'quant-trading': {
    prerequisites: 'Python 3.10+, basic probability and statistics',
    recommended: 'Introduction to programming',
  },
}

export default function CatalogPage() {
  const courses = activeCourses()

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="The catalogue"
            title={
              <>
                Pick a <em className="italic text-accent">learning track</em>
              </>
            }
            lead="Each course is self-contained. Every exercise runs locally against standard libraries with zero external dependencies and sub-second grading."
          />

          <RuledList>
            {courses.map((course, index) => {
              const modules = activeModules(course)
              const lessons = modules.reduce((n, m) => n + m.lessons.length, 0)
              const exercises = modules.reduce(
                (n, m) => n + m.lessons.filter((l) => l.exercise).length,
                0,
              )
              const hours = modules.reduce((n, m) => n + m.estimatedHours, 0)
              const reqs = COURSE_REQUIREMENTS[course.slug] || {
                prerequisites: 'Python 3.10+',
                recommended: null,
              }

              return (
                <RuledRow
                  key={course.id}
                  index={index}
                  aside={String(course.order + 1).padStart(2, '0')}
                  title={course.name}
                  meta={`${modules.length} modules · ${lessons} lessons · ${exercises} exercises · ${Math.round(hours)}h`}
                  href={`/learn/${course.slug}`}
                >
                  <p className="text-ink-soft">{course.summary}</p>

                  <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-caption">
                    <span className="text-muted">
                      <span className="font-medium text-ink-soft">Prerequisites:</span>{' '}
                      <span className={reqs.prerequisites === 'None' ? 'text-accent font-medium' : 'text-ink-soft'}>
                        {reqs.prerequisites}
                      </span>
                    </span>
                    {reqs.recommended && (
                      <span className="text-muted">
                        <span className="font-medium text-ink-soft">Recommended:</span> {reqs.recommended}
                      </span>
                    )}
                  </div>

                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {course.tracks.map((t) => (
                      <span
                        key={t.id}
                        className="font-mono text-[11px] uppercase tracking-wider text-muted"
                      >
                        [{t.name}]
                      </span>
                    ))}
                  </div>
                </RuledRow>
              )
            })}
          </RuledList>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
