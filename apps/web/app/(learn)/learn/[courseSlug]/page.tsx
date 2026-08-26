import { notFound } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Eyebrow, PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeCourses, activeModules, findCourse, prerequisiteNames } from '@/lib/content'
import { accessFor, canOpen } from '@/lib/server/access'
import { currentUser } from '@/lib/server/session'

export function generateStaticParams() {
  return activeCourses().map((course) => ({ courseSlug: course.slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ courseSlug: string }>
}): Promise<Metadata> {
  const course = findCourse((await params).courseSlug)
  if (!course) return { title: 'Not found' }
  return { title: course.name, description: course.summary }
}

const COURSE_REQUIREMENTS: Record<
  string,
  { prerequisites: string; recommended: string | null; audience: string }
> = {
  'intro-programming': {
    prerequisites: 'None',
    recommended: 'Start here if new to low-level memory, systems programming, or C/C++',
    audience: 'Engineers wanting to understand physical memory in C, RAII in C++, and dynamic runtimes in Python.',
  },
  'ai-agents': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming (Modules 00–04)',
    audience: 'Engineers building autonomous loops, tool schemas, multi-agent systems, and eval harnesses.',
  },
  'data-engineering': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming (Modules 00–01)',
    audience: 'Engineers building idempotent pipelines, quarantine validators, SQLite storage, and data contracts.',
  },
  'quant-trading': {
    prerequisites: 'Python 3.10+, basic probability and statistics',
    recommended: 'Introduction to programming',
    audience: 'Engineers building limit order books, time-series signals, event-driven backtesting, and portfolio risk systems.',
  },
}

export default async function CoursePage({
  params,
}: {
  params: Promise<{ courseSlug: string }>
}) {
  const { courseSlug } = await params
  const course = findCourse(courseSlug)
  if (!course) notFound()

  const modules = activeModules(course)
  const user = await currentUser()
  const access = await accessFor(user?.id)

  const reqs = COURSE_REQUIREMENTS[course.slug] || {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming',
    audience: course.summary,
  }

  // Tracks come from the course's own `course.yaml`.
  const tracks = course.tracks.filter((track) =>
    modules.some((module) => module.track === track.id),
  )

  const totalLessons = modules.reduce((n, m) => n + m.lessons.length, 0)
  const totalExercises = modules.reduce(
    (n, m) => n + m.lessons.filter((l) => l.exercise).length,
    0,
  )
  const totalHours = Math.round(modules.reduce((n, m) => n + m.estimatedHours, 0))

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow={`Learning Track · ${modules.length} Modules · ${totalLessons} Lessons · ${totalExercises} Exercises · ${totalHours}h`}
            title={
              <>
                The <em className="italic text-accent">{course.name}</em> curriculum
              </>
            }
            lead={course.summary}
          />

          {/* Prerequisites and Focus Card */}
          <Reveal delay={0.08}>
            <div className="mt-10 border border-rule bg-paper-raised p-6">
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <p className="text-eyebrow font-medium uppercase text-muted">
                    Prerequisites & Preparation
                  </p>
                  <p className="mt-2 font-serif text-ink">
                    <span className="font-medium text-ink">Prerequisites:</span>{' '}
                    <span className={reqs.prerequisites === 'None' ? 'text-accent font-medium' : 'text-ink-soft'}>
                      {reqs.prerequisites}
                    </span>
                  </p>
                  {reqs.recommended && (
                    <p className="mt-1.5 text-caption text-muted">
                      <span className="font-medium text-ink-soft">Recommended:</span> {reqs.recommended}
                    </p>
                  )}
                  <p className="mt-2 text-caption text-muted">
                    <span className="font-medium text-ink-soft">Scope:</span> {reqs.audience}
                  </p>
                </div>

                <div>
                  <p className="text-eyebrow font-medium uppercase text-muted">
                    Track Architecture
                  </p>
                  <ul className="mt-2 space-y-1.5 text-caption">
                    {course.tracks.map((t) => (
                      <li key={t.id} className="text-ink-soft">
                        <span className="font-mono text-muted">[{t.id}]</span>{' '}
                        <span className="font-medium text-ink">{t.name}:</span>{' '}
                        <span className="text-muted">{t.note || ''}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </Reveal>

          {tracks.map((track) => (
            <section key={track.id} className="mt-16 first:mt-12">
              <Reveal>
                <Eyebrow>{track.name}</Eyebrow>
                {track.note && <p className="mt-2 max-w-[56ch] text-ink-soft">{track.note}</p>}
              </Reveal>

              <RuledList>
                {modules
                  .filter((module) => module.track === track.id)
                  .map((module, index) => (
                    <RuledRow
                      key={module.id}
                      index={index}
                      aside={String(module.order).padStart(2, '0')}
                      title={module.name}
                      meta={
                        canOpen(access, course, module)
                          ? `${module.lessons.length} lessons · ${module.estimatedHours}h · ${module.difficulty}`
                          : `${module.lessons.length} lessons · ${module.estimatedHours}h · not yet`
                      }
                      href={`/learn/${course.slug}/${module.slug}`}
                    >
                      <p className="text-ink-soft">{module.summary}</p>
                      {module.prerequisites.length > 0 ? (
                        <p className="mt-2 text-caption text-muted">
                          <span className="font-medium text-ink-soft">Requires:</span>{' '}
                          {prerequisiteNames(course, module.prerequisites)}
                        </p>
                      ) : (
                        <p className="mt-2 text-caption text-muted">
                          <span className="text-ink-soft">No prerequisites</span> · First module in track
                        </p>
                      )}
                    </RuledRow>
                  ))}
              </RuledList>
            </section>
          ))}
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
