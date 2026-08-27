import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { LessonBody } from '@/components/lesson-body'
import { LessonSidebar } from '@/components/lesson-sidebar'
import { CompleteButton } from '@/components/complete-button'
import { ExerciseCallout } from '@/components/exercise-callout'
import { everyLesson, findCourse, findLesson, loadLesson, neighbours } from '@/lib/content'
import { accessFor, blockedBy, canOpen } from '@/lib/server/access'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { Locked } from '@/components/locked'
import { LessonStageController, WidgetRegistry } from '@atlas/ui'

type Params = Promise<{ courseSlug: string; moduleSlug: string; lessonSlug: string }>

export function generateStaticParams() {
  return everyLesson().map(({ course, module, lesson }) => ({
    courseSlug: course.slug,
    moduleSlug: module.slug,
    lessonSlug: lesson.slug,
  }))
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { courseSlug, moduleSlug, lessonSlug } = await params
  const course = findCourse(courseSlug)
  const found = course && findLesson(course, moduleSlug, lessonSlug)
  return found ? { title: found.lesson.title, description: found.lesson.summary } : {}
}

export default async function LessonPage({ params }: { params: Params }) {
  const { courseSlug, moduleSlug, lessonSlug } = await params

  const course = findCourse(courseSlug)
  if (!course) notFound()

  const found = findLesson(course, moduleSlug, lessonSlug)
  if (!found) notFound()

  const { module, lesson } = found
  const compiled = await loadLesson(lesson.id)
  if (!compiled) notFound()

  const { previous, next } = neighbours(course, lesson.id)

  // Reading is open to everyone. Only progress state needs a session.
  const user = await currentUser()

  // The gate. Enforced here, on the server, where the body actually is: a
  // client-side check would ship the lesson and then hide it, which is not a
  // gate, it is a curtain.
  const access = await accessFor(user?.id)
  const unlocked = canOpen(access, course, module)
  const completed = user
    ? (await store().progressFor(user.id)).lessons.some(
        (row) => row.lessonId === lesson.id && row.status === 'completed',
      )
    : false

  return (
    <>
      <SiteHeader />

      <div className="mx-auto w-full max-w-[1600px] px-6 pt-6 pb-24 sm:px-10 sm:pt-8">
        {!unlocked ? (
          <div className="flex flex-col lg:flex-row lg:gap-14">
            <LessonSidebar module={module} courseSlug={course.slug} activeLessonId={lesson.id} />
            <main id="main" className="min-w-0 flex-1">
              <header className="max-w-[62ch]">
                <p className="text-eyebrow font-medium uppercase text-muted">
                  <Link
                    href={`/learn/${course.slug}/${module.slug}`}
                    className="transition-colors duration-200 ease-paper hover:text-ink"
                  >
                    {module.name}
                  </Link>
                </p>
                <h1 className="mt-4 text-title text-ink">{lesson.title}</h1>
                <p className="mt-4 max-w-[56ch] font-serif text-lead text-ink-soft">
                  {lesson.summary}
                </p>
              </header>
              <hr className="mt-8 mb-8 border-rule" />
              <Locked
                blockedBy={blockedBy(access, course, module).map((m) => ({
                  name: m.name,
                  slug: m.slug,
                }))}
                courseSlug={course.slug}
                signedIn={access.signedIn}
              />
            </main>
          </div>
        ) : (
          (() => {
            const InteractiveComponent = compiled.interactive
              ? WidgetRegistry[compiled.interactive.type]
              : null

            const headerNode = (
              <div>
                <header className="max-w-[62ch]">
                  <p className="text-eyebrow font-medium uppercase text-muted">
                    <Link
                      href={`/learn/${course.slug}/${module.slug}`}
                      className="transition-colors duration-200 ease-paper hover:text-ink"
                    >
                      {module.name}
                    </Link>
                  </p>

                  <h1 className="mt-3 text-title text-ink">{lesson.title}</h1>
                  <p className="mt-3 max-w-[56ch] font-serif text-lead text-ink-soft">
                    {lesson.summary}
                  </p>
                  <p className="mt-3 text-caption text-muted">
                    {lesson.estimatedMinutes} minute read
                    {completed && ' · completed'}
                  </p>
                </header>

                <hr className="mt-6 mb-6 border-rule" />

                {/* Desktop App Banner Callout */}
                <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-lg border border-rule bg-paper-sunken px-4 py-3 text-caption">
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent/10 font-mono text-xs font-bold text-accent">
                      ⚡
                    </span>
                    <div>
                      <span className="font-semibold text-ink">For the best experience:</span>{' '}
                      <span className="text-ink-soft">
                        Download the native Atlas Desktop app for instant test running, native IDE sync, and 100% offline practice.
                      </span>
                    </div>
                  </div>
                  <Link
                    href="/download"
                    className="shrink-0 inline-flex items-center gap-1.5 rounded border border-rule-strong bg-paper px-3 py-1.5 font-mono text-[11px] font-semibold text-ink hover:border-accent hover:text-accent transition-colors self-start sm:self-auto"
                  >
                    <span>Download Desktop App</span>
                    <span>&rarr;</span>
                  </Link>
                </div>
              </div>
            )

            const footerNode = (
              <div>
                {user && unlocked ? (
                  <CompleteButton
                    lessonId={lesson.id}
                    moduleId={module.id}
                    initiallyComplete={completed}
                  />
                ) : user ? null : (
                  <Link
                    href={`/login?next=/learn/${course.slug}/${module.slug}/${lesson.slug}`}
                    className="inline-flex min-h-11 items-center rounded-field border border-rule-strong px-5 text-caption font-medium text-ink transition-colors duration-200 ease-paper hover:bg-paper-raised"
                  >
                    Sign in to track progress
                  </Link>
                )}
                <nav
                  aria-label="Lesson"
                  className="mt-10 grid gap-px border-t border-rule sm:grid-cols-2"
                >
                  {previous ? (
                    <Link
                      href={`/learn/${course.slug}/${previous.module.slug}/${previous.lesson.slug}`}
                      className="group py-6 transition-colors duration-200 ease-paper hover:bg-paper-raised sm:pr-8"
                    >
                      <span className="text-caption text-muted">Previous</span>
                      <span className="mt-1 block text-ink-soft transition-colors duration-200 ease-paper group-hover:text-ink">
                        {previous.lesson.title}
                      </span>
                    </Link>
                  ) : (
                    <span />
                  )}

                  {next && (
                    <Link
                      href={`/learn/${course.slug}/${next.module.slug}/${next.lesson.slug}`}
                      className="group border-t border-rule py-6 transition-colors duration-200 ease-paper hover:bg-paper-raised sm:border-t-0 sm:border-l sm:pl-8 sm:text-right"
                    >
                      <span className="text-caption text-muted">Next</span>
                      <span className="mt-1 block text-ink-soft transition-colors duration-200 ease-paper group-hover:text-ink">
                        {next.lesson.title}
                      </span>
                    </Link>
                  )}
                </nav>
              </div>
            )

            return (
              <main id="main" className="w-full">
                <LessonStageController
                  hasInteractive={Boolean(InteractiveComponent)}
                  hasExercise={Boolean(lesson.exercise)}
                  interactiveNode={
                    InteractiveComponent ? (
                      <InteractiveComponent {...(compiled.interactive?.props || {})} />
                    ) : null
                  }
                  headerNode={headerNode}
                  sidebarNode={
                    <LessonSidebar module={module} courseSlug={course.slug} activeLessonId={lesson.id} />
                  }
                  proseNode={<LessonBody html={compiled.html} />}
                  exerciseNode={
                    lesson.exercise ? (
                      <ExerciseCallout
                        exerciseId={lesson.exercise.id}
                        timeboxMinutes={lesson.exercise.timeboxMinutes}
                        files={compiled.exerciseFiles}
                        browser={lesson.exercise.browser}
                      />
                    ) : null
                  }
                  footerNode={footerNode}
                />
              </main>
            )
          })()
        )}
      </div>

      <SiteFooter />
    </>
  )
}
