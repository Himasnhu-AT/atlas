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
import { accessFor, canOpen } from '@/lib/server/access'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { Paywall } from '@/components/paywall'

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

      <div className="mx-auto w-full max-w-page px-6 pt-10 pb-24 sm:px-8 sm:pt-14">
        {/* Stacked until there is room for a margin column. Without the
            column direction the mobile contents disclosure becomes a flex
            sibling of the article and squeezes it into a few characters. */}
        <div className="flex flex-col lg:flex-row lg:gap-14">
          <LessonSidebar module={module} activeLessonId={lesson.id} />

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
              <p className="mt-4 text-caption text-muted">
                {lesson.estimatedMinutes} minute read
                {completed && ' · completed'}
              </p>
            </header>

            <hr className="mt-10 mb-12 border-rule" />

            {!unlocked ? (
              <Paywall courseName={course.name} signedIn={access.signedIn} />
            ) : (
              <LessonBody html={compiled.html} />
            )}

            {unlocked && lesson.exercise && (
              <ExerciseCallout
                exerciseId={lesson.exercise.id}
                timeboxMinutes={lesson.exercise.timeboxMinutes}
                files={compiled.exerciseFiles}
              />
            )}

            <div className="mt-16 border-t border-rule pt-8">
              {/* No completing what you cannot read. The endpoint refuses it
                  too; this is so nobody is offered a button that will fail. */}
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
          </main>
        </div>
      </div>

      <SiteFooter />
    </>
  )
}
