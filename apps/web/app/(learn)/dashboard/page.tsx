import Link from 'next/link'
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'
import { currentStreak, modulePercent } from '@learn/core'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeModules, lessonSequence, prerequisiteNames } from '@/lib/content'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

export const metadata: Metadata = { title: 'Progress' }

export default async function DashboardPage() {
  const user = await currentUser()
  if (!user) redirect('/login?next=/dashboard')

  const snapshot = await store().progressFor(user.id)
  const modules = activeModules()
  const streak = currentStreak(snapshot.activity, new Date().toISOString().slice(0, 10))

  const completedModuleIds = new Set(
    snapshot.modules.filter((row) => row.status === 'completed').map((row) => row.moduleId),
  )
  const completedLessonIds = new Set(
    snapshot.lessons.filter((row) => row.status === 'completed').map((row) => row.lessonId),
  )

  const sequence = lessonSequence()
  // The next unfinished lesson beats the most recently opened one: after
  // finishing a module, "resume" should move you forward, not back.
  const resume = sequence.find(({ lesson }) => !completedLessonIds.has(lesson.id))
  const totalLessons = sequence.length
  // Count against the course as it stands. A rebuilt module can rename or drop
  // a lesson, and the progress row for the old id outlives it, so counting the
  // rows would say "41 of 40 lessons done".
  const completedInCourse = sequence.filter(({ lesson }) =>
    completedLessonIds.has(lesson.id),
  ).length
  const firstName = user.displayName.split(' ')[0]

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="Your progress"
            title={
              <>
                Welcome back, <em className="italic text-accent">{firstName}</em>.
              </>
            }
            lead={
              completedInCourse === 0
                ? 'Nothing finished yet. Module 0 takes about an hour and ends with a passing test.'
                : `${completedInCourse} of ${totalLessons} lessons done${
                    streak > 0
                      ? `, and you have worked ${streak} day${streak === 1 ? '' : 's'} running.`
                      : '.'
                  }`
            }
          />

          {resume ? (
            <Reveal delay={0.2}>
              <Link
                href={`/learn/${resume.module.slug}/${resume.lesson.slug}`}
                className="group mt-14 block border-y-2 border-ink py-8 transition-colors duration-200 ease-paper hover:bg-paper-raised"
              >
                <p className="text-eyebrow font-medium uppercase text-muted">
                  {completedInCourse === 0 ? 'Start here' : 'Pick up where you left off'}
                </p>
                <p className="mt-3 flex items-baseline gap-3 text-title text-ink">
                  {resume.lesson.title}
                  <span
                    aria-hidden
                    className="text-lead transition-transform duration-200 ease-paper group-hover:translate-x-2"
                  >
                    &rarr;
                  </span>
                </p>
                <p className="mt-3 text-caption text-muted">
                  {resume.module.name} · {resume.lesson.estimatedMinutes} min
                </p>
              </Link>
            </Reveal>
          ) : (
            <Reveal delay={0.2}>
              <div className="mt-14 border-y-2 border-pass py-8">
                <p className="text-title text-ink">You finished every lesson.</p>
                <p className="mt-3 max-w-[52ch] text-ink-soft">
                  Go build something with it. New modules land here when they are ready.
                </p>
              </div>
            </Reveal>
          )}

          <RuledList>
            {modules.map((module, index) => {
              // Both numbers come from the lesson rows and the module as it
              // stands today. Taking the count from the stored rollup and the
              // total from the manifest is what produced a bar at 50% next to
              // a label reading "1 of 3": the rollup is only recomputed when
              // the student next completes a lesson in that module, so it
              // still held the lesson count from before the content changed.
              const done = module.lessons.filter((lesson) =>
                completedLessonIds.has(lesson.id),
              ).length
              const percent = modulePercent({
                moduleId: module.id,
                status: 'available',
                lessonsCompleted: done,
                lessonsTotal: module.lessons.length,
              })
              const locked = !module.prerequisites.every((id) => completedModuleIds.has(id))

              return (
                <RuledRow
                  key={module.id}
                  index={index}
                  aside={String(module.order).padStart(2, '0')}
                  title={module.name}
                  meta={`${done} of ${module.lessons.length}`}
                  href={`/learn/${module.slug}`}
                >
                  {/* A hairline that fills, rather than a ring or a pill. The
                      page already has rules everywhere; progress is one of them
                      drawn partway. */}
                  <div
                    className="mt-1 h-px w-full max-w-sm bg-rule"
                    role="progressbar"
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${module.name}: ${percent}% complete`}
                  >
                    <div
                      className="h-px bg-accent transition-[width] duration-500 ease-paper"
                      style={{ width: `${percent}%` }}
                    />
                  </div>

                  {locked && (
                    <p className="mt-3 text-caption text-muted">
                      Opens after {prerequisiteNames(module.prerequisites)}
                    </p>
                  )}
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
