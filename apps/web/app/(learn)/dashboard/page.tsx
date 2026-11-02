import Link from 'next/link'
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'
import { modulePercent } from '@atlas/core'

import { RankStamp, WeekDots } from '@atlas/ui/game'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Eyebrow, RuledList, RuledRow } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeCourses, activeModules, lessonSequence, prerequisiteNames } from '@/lib/content'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { gameStateFor } from '@/lib/server/xp'

export const metadata: Metadata = { title: 'Progress & Tracks' }

interface CourseRequirement {
  prerequisites: string
  recommended: string | null
  level: string
  audience: string
}

const COURSE_REQUIREMENTS: Record<string, CourseRequirement> = {
  'intro-programming': {
    prerequisites: 'None',
    recommended: null,
    level: 'Beginner',
    audience: 'Physical memory in C, RAII in C++, and dynamic runtimes in Python.',
  },
  'ai-agents': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'Introduction to programming',
    level: 'Intermediate',
    audience: 'Autonomous agent architectures, tool loops, RAG pipelines, and multi-agent systems.',
  },
  'data-engineering': {
    prerequisites: 'Python 3.10+ standard library',
    recommended: 'None',
    level: 'Beginner',
    audience: 'Deterministic data handling, quarantine validation, SQLite storage, and pipelines.',
  },
  'quant-trading': {
    prerequisites: 'Python 3.10+, basic probability',
    recommended: 'Introduction to programming',
    level: 'Intermediate',
    audience: 'Limit order books, time series signals, event-driven backtesting, and risk models.',
  },
}

interface DashboardPageProps {
  searchParams?: Promise<{ track?: string; course?: string }>
}

export default async function DashboardPage(props: DashboardPageProps) {
  const user = await currentUser()
  if (!user) redirect('/login?next=/dashboard')

  const searchParams = props.searchParams ? await props.searchParams : {}
  const activeTrackParam = searchParams.track || searchParams.course || 'all'

  const snapshot = await store().progressFor(user.id)
  const courses = activeCourses()
  const game = await gameStateFor(user.id)

  const completedModuleIds = new Set(
    snapshot.modules.filter((row) => row.status === 'completed').map((row) => row.moduleId),
  )
  const completedLessonIds = new Set(
    snapshot.lessons.filter((row) => row.status === 'completed').map((row) => row.lessonId),
  )

  // Compute progress for each course
  const courseStats = new Map(
    courses.map((course) => {
      const seq = lessonSequence(course)
      const done = seq.filter(({ lesson }) => completedLessonIds.has(lesson.id)).length
      const total = seq.length
      const percent = total === 0 ? 0 : Math.round((done / total) * 100)
      return [course.slug, { done, total, percent, seq }]
    }),
  )

  // Active track selection
  const selectedCourse = courses.find((c) => c.slug === activeTrackParam || c.id === activeTrackParam)
  const isAllTracks = !selectedCourse || activeTrackParam === 'all'

  // Scoped sequence for resume action
  const activeSequence = selectedCourse
    ? lessonSequence(selectedCourse).map((entry) => ({ ...entry, course: selectedCourse }))
    : courses.flatMap((course) =>
        lessonSequence(course).map((entry) => ({ ...entry, course })),
      )

  const resume = activeSequence.find(({ lesson }) => !completedLessonIds.has(lesson.id))
  const completedInActive = activeSequence.filter(({ lesson }) =>
    completedLessonIds.has(lesson.id),
  ).length

  const isFirstTimeUser = completedInActive === 0
  const firstName = user.displayName.split(' ')[0]

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-16 pb-24 sm:pt-20">
        <div className="mx-auto w-full max-w-7xl px-6 sm:px-8 lg:px-10">
          {/* Top Hero: Greeting, Telemetry & Desktop Download */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:items-center">
            {/* Left: User Welcome */}
            <div className="lg:col-span-7">
              <Reveal>
                <Eyebrow>Your learning dashboard</Eyebrow>
                <h1 className="mt-2 font-serif text-[32px] sm:text-[40px] font-medium leading-tight text-ink">
                  {isFirstTimeUser ? 'Welcome to Atlas, ' : 'Welcome back, '}
                  <em className="italic text-accent">{firstName}</em>.
                </h1>
                <p className="mt-3 max-w-[50ch] text-caption text-ink-soft sm:text-[15px]">
                  All tracks run in an isolated in-browser sandbox with zero configuration. You can also run exercises locally with our desktop app.
                </p>
              </Reveal>
            </div>

            {/* Right: Desktop App CTA + Telemetry Card */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              <Reveal delay={0.1}>
                {/* Desktop App Banner */}
                <div className="flex items-center justify-between rounded-sheet border border-rule bg-paper-raised/70 p-4 shadow-xs">
                  <div className="pr-3">
                    <div className="flex items-center gap-2">
                      <span className="inline-block size-2 rounded-full bg-accent" />
                      <p className="font-serif text-[15px] font-medium text-ink">Atlas Workbench</p>
                    </div>
                    <p className="mt-0.5 text-[12px] text-muted">
                      Three panes: lesson, editor & terminal.
                    </p>
                  </div>
                  <Link
                    href="/download"
                    className="shrink-0 inline-flex items-center gap-1.5 rounded-field bg-ink px-3.5 py-2 text-[12px] font-medium text-paper transition-colors hover:bg-accent-deep"
                  >
                    <span>Download App</span>
                    <span aria-hidden>&rarr;</span>
                  </Link>
                </div>

                {/* Level & Streak Telemetry */}
                <div className="mt-3 flex items-center justify-between rounded-sheet border border-rule bg-paper p-4 text-caption shadow-xs">
                  <div className="flex items-center gap-3">
                    <span className="shrink-0 text-accent">
                      <RankStamp
                        roman={game.level.rank.roman}
                        title={`Rank ${game.level.rank.roman}, ${game.level.rank.name}`}
                      />
                    </span>
                    <div>
                      <p className="font-medium text-ink">
                        Level {game.level.level} · {game.level.rank.name}
                      </p>
                      <p className="font-mono text-[11px] text-muted">{game.level.totalXp} XP earned</p>
                    </div>
                  </div>

                  <Link
                    href="/ledger"
                    className="flex items-center gap-2.5 text-muted transition-colors hover:text-ink"
                  >
                    <WeekDots daysActive={game.week.daysActive} target={game.week.target} />
                    <span className="text-[12px] font-mono">{game.week.daysActive}/{game.week.target}d</span>
                    <span aria-hidden>&rarr;</span>
                  </Link>
                </div>
              </Reveal>
            </div>
          </div>

          {/* Quick Resume Hero: 1-Click Launch */}
          {resume ? (
            <Reveal delay={0.15}>
              <Link
                href={`/learn/${resume.course.slug}/${resume.module.slug}/${resume.lesson.slug}`}
                className="group mt-8 flex flex-wrap items-center justify-between gap-4 rounded-sheet border border-rule bg-paper-raised/50 px-6 py-4.5 transition-all duration-200 hover:border-ink hover:bg-paper-raised shadow-xs"
              >
                <div className="flex items-center gap-4">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-paper text-caption font-mono">
                    ▶
                  </span>
                  <div>
                    <p className="text-[11px] font-mono uppercase tracking-wider text-muted">
                      {isFirstTimeUser
                        ? `Recommended First Step · ${resume.course.name}`
                        : `Resume Learning · ${resume.course.name}`}
                    </p>
                    <p className="font-serif text-[18px] font-medium text-ink group-hover:text-accent transition-colors">
                      {resume.lesson.title}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-caption font-medium text-ink">
                  <span className="font-mono text-muted text-[12px]">{resume.lesson.estimatedMinutes} min</span>
                  <span className="transition-transform duration-200 group-hover:translate-x-1">&rarr;</span>
                </div>
              </Link>
            </Reveal>
          ) : (
            <Reveal delay={0.15}>
              <div className="mt-8 rounded-sheet border border-pass bg-paper-raised/50 p-5">
                <p className="font-serif text-[18px] font-medium text-ink">
                  {selectedCourse
                    ? `You finished every lesson in ${selectedCourse.name}.`
                    : 'You finished every lesson across all available tracks.'}
                </p>
                <p className="mt-1 text-caption text-ink-soft">
                  Review your reference solutions or build a custom project.
                </p>
              </div>
            </Reveal>
          )}

          {/* Track Filter Navigation */}
          <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-rule pt-6">
            <div className="flex items-center gap-2">
              <span className="font-serif text-[16px] font-medium text-ink">All Learning Tracks</span>
              <span className="font-mono text-[12px] text-muted">({courses.length} courses · 31 modules)</span>
            </div>

            <nav aria-label="Course Tracks" className="flex flex-wrap gap-2">
              <Link
                href="/dashboard?track=all"
                scroll={false}
                className={`rounded-field px-3 py-1.5 text-[12px] font-medium transition-colors ${
                  isAllTracks
                    ? 'bg-ink text-paper shadow-xs'
                    : 'border border-rule bg-paper/60 text-ink-soft hover:bg-paper-raised hover:text-ink'
                }`}
              >
                All Courses Grid
              </Link>

              {courses.map((course) => {
                const isSelected = selectedCourse?.id === course.id
                const stats = courseStats.get(course.slug)
                return (
                  <Link
                    key={course.id}
                    href={`/dashboard?track=${course.slug}`}
                    scroll={false}
                    className={`rounded-field px-3 py-1.5 text-[12px] font-medium transition-colors ${
                      isSelected
                        ? 'bg-ink text-paper shadow-xs'
                        : 'border border-rule bg-paper/60 text-ink-soft hover:bg-paper-raised hover:text-ink'
                    }`}
                  >
                    <span>{course.name}</span>
                    {stats && stats.total > 0 && (
                      <span
                        className={`ml-1.5 font-mono text-[10.5px] tabular-nums ${
                          isSelected
                            ? 'text-paper/70'
                            : stats.done === stats.total
                              ? 'text-pass'
                              : stats.done > 0
                                ? 'text-accent'
                                : 'text-muted'
                        }`}
                      >
                        {stats.done}/{stats.total}
                      </span>
                    )}
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* VIEW MODE 1: Full-Width 4-Course 2x2 Grid (All Courses visible above the fold) */}
          {isAllTracks && (
            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
              {courses.map((course, index) => {
                const stats = courseStats.get(course.slug)
                const reqs = COURSE_REQUIREMENTS[course.slug]
                const done = stats?.done ?? 0
                const total = stats?.total ?? 0
                const percent = stats?.percent ?? 0
                const modules = activeModules(course)
                const firstLesson = modules[0]?.lessons[0]

                return (
                  <div
                    key={course.id}
                    className="flex flex-col justify-between rounded-sheet border border-rule bg-paper-raised/40 p-6 transition-all duration-200 hover:border-rule-strong hover:bg-paper-raised/70 shadow-xs"
                  >
                    <div>
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[12px] text-muted">0{index + 1}</span>
                        <div className="flex items-center gap-2">
                          <span className="rounded-full border border-rule bg-paper px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
                            {reqs?.level ?? 'Track'}
                          </span>
                          <span className="font-mono text-[11px] text-muted">
                            {modules.length} modules · {total} lessons
                          </span>
                        </div>
                      </div>

                      {/* Course Title & Focus */}
                      <h3 className="mt-3 font-serif text-[21px] font-medium text-ink">
                        {course.name}
                      </h3>
                      <p className="mt-2 text-caption text-ink-soft line-clamp-2">
                        {course.summary}
                      </p>

                      {/* Prerequisites */}
                      <p className="mt-3 text-[12px] text-muted">
                        <span className="font-medium text-ink-soft">Prereqs:</span> {reqs?.prerequisites ?? 'None'}
                      </p>
                    </div>

                    {/* Bottom Progress & Action */}
                    <div className="mt-6 border-t border-rule pt-4">
                      <div className="flex items-center justify-between text-[12px] font-mono text-muted mb-2">
                        <span>Progress</span>
                        <span>{done}/{total} ({percent}%)</span>
                      </div>
                      <div
                        className="h-1.5 w-full rounded-full bg-rule overflow-hidden"
                        role="progressbar"
                        aria-valuenow={percent}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div
                          className="h-full bg-accent transition-[width] duration-500 ease-paper"
                          style={{ width: `${percent}%` }}
                        />
                      </div>

                      <div className="mt-4 flex items-center justify-between gap-3">
                        <Link
                          href={`/dashboard?track=${course.slug}`}
                          className="text-[12px] font-medium text-muted hover:text-ink hover:underline"
                        >
                          View modules →
                        </Link>

                        <Link
                          href={firstLesson ? `/learn/${course.slug}/${modules[0]?.slug}/${firstLesson.slug}` : `/learn/${course.slug}`}
                          className="inline-flex items-center gap-1.5 rounded-field bg-ink px-3.5 py-1.5 text-[12px] font-medium text-paper transition-colors hover:bg-accent-deep"
                        >
                          <span>{done > 0 ? 'Continue' : 'Start Track'}</span>
                          <span aria-hidden>&rarr;</span>
                        </Link>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* VIEW MODE 2: Single Course Track Deep Dive */}
          {selectedCourse && (
            <section className="mt-6">
              {(() => {
                const reqs = COURSE_REQUIREMENTS[selectedCourse.slug]
                const stats = courseStats.get(selectedCourse.slug)
                const modules = activeModules(selectedCourse)

                return (
                  <div>
                    <div className="rounded-sheet border border-rule bg-paper-raised/60 p-6">
                      <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-rule pb-4">
                        <div>
                          <Eyebrow>{reqs?.level ?? 'Track'} Track</Eyebrow>
                          <h2 className="mt-1 font-serif text-[24px] font-medium text-ink">{selectedCourse.name}</h2>
                        </div>
                        {stats && (
                          <span className="font-mono text-caption text-muted">
                            {stats.done} of {stats.total} lessons ({stats.percent}%)
                          </span>
                        )}
                      </div>

                      <div className="mt-4 grid gap-6 sm:grid-cols-2 text-caption">
                        <div>
                          <p className="font-medium text-ink">Prerequisites & Focus</p>
                          <p className="mt-1 text-ink-soft">
                            <span className="font-medium text-muted">Prerequisites:</span> {reqs?.prerequisites}
                          </p>
                          {reqs?.recommended && (
                            <p className="mt-1 text-muted">
                              <span className="font-medium text-ink-soft">Recommended:</span> {reqs.recommended}
                            </p>
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-ink">Sub-Tracks ({selectedCourse.tracks.length})</p>
                          <p className="mt-1 text-muted">
                            {selectedCourse.tracks.map((t) => t.name).join(' · ')}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Modules Ruled List */}
                    <div className="mt-8">
                      <RuledList>
                        {modules.map((module, index) => {
                          const done = module.lessons.filter((lesson) =>
                            completedLessonIds.has(lesson.id),
                          ).length
                          const percent = modulePercent({
                            moduleId: module.id,
                            status: 'available',
                            lessonsCompleted: done,
                            lessonsTotal: module.lessons.length,
                          })
                          const hasPrereqs = module.prerequisites.length > 0
                          const locked = !module.prerequisites.every((id) =>
                            completedModuleIds.has(id),
                          )

                          return (
                            <RuledRow
                              key={module.id}
                              index={index}
                              aside={String(module.order).padStart(2, '0')}
                              title={
                                <span className="inline-flex items-center gap-2">
                                  {module.name}
                                  <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
                                    [{module.track}]
                                  </span>
                                </span>
                              }
                              meta={`${done} of ${module.lessons.length} lessons`}
                              href={`/learn/${selectedCourse.slug}/${module.slug}`}
                            >
                              <p className="text-ink-soft">{module.summary}</p>

                              {/* Progress bar */}
                              <div
                                className="mt-3 h-1 w-full max-w-sm rounded-full bg-rule overflow-hidden"
                                role="progressbar"
                                aria-valuenow={percent}
                                aria-valuemin={0}
                                aria-valuemax={100}
                              >
                                <div
                                  className="h-full bg-accent transition-[width] duration-500 ease-paper"
                                  style={{ width: `${percent}%` }}
                                />
                              </div>

                              {/* Prerequisite status */}
                              <div className="mt-2.5 text-[12px]">
                                {locked ? (
                                  <p className="text-muted">
                                    <span className="font-medium text-warn">Locked</span> · Opens after{' '}
                                    <span className="font-medium text-ink-soft">
                                      {prerequisiteNames(selectedCourse, module.prerequisites)}
                                    </span>
                                  </p>
                                ) : hasPrereqs ? (
                                  <p className="text-muted">
                                    <span className="font-medium text-pass">Prerequisites:</span>{' '}
                                    <span>{prerequisiteNames(selectedCourse, module.prerequisites)}</span>
                                  </p>
                                ) : (
                                  <p className="text-muted">
                                    <span className="text-ink-soft">No prerequisites</span> · First module in track
                                  </p>
                                )}
                              </div>
                            </RuledRow>
                          )
                        })}
                      </RuledList>
                    </div>
                  </div>
                )
              })()}
            </section>
          )}
        </div>
      </main>

      <SiteFooter />
    </>
  )
}
