import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeCourses, activeModules, findCourse, findModule, prerequisiteNames } from '@/lib/content'

type Params = Promise<{ courseSlug: string; moduleSlug: string }>

export function generateStaticParams() {
  return activeCourses().flatMap((course) =>
    activeModules(course).map((module) => ({
      courseSlug: course.slug,
      moduleSlug: module.slug,
    })),
  )
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { courseSlug, moduleSlug } = await params
  const course = findCourse(courseSlug)
  const module = course && findModule(course, moduleSlug)
  return module ? { title: module.name, description: module.summary } : {}
}

export default async function ModulePage({ params }: { params: Params }) {
  const { courseSlug, moduleSlug } = await params
  const course = findCourse(courseSlug)
  if (!course) notFound()
  const module = findModule(course, moduleSlug)
  if (!module) notFound()

  const lessons = [...module.lessons].sort((a, b) => a.order - b.order)
  const exercises = lessons.filter((lesson) => lesson.exercise).length
  const trackObj = course.tracks.find((t) => t.id === module.track)

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <Reveal>
            <Link
              href={`/learn/${course.slug}`}
              className="group inline-flex min-h-11 items-center gap-2 text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink"
            >
              <span
                aria-hidden
                className="transition-transform duration-200 ease-paper group-hover:-translate-x-1"
              >
                &larr;
              </span>
              Back to {course.name}
            </Link>
          </Reveal>

          <div className="mt-4">
            <PageHeader
              eyebrow={`Module ${String(module.order).padStart(2, '0')} · ${trackObj?.name || module.track}`}
              title={module.name}
              lead={module.summary}
            />
          </div>

          <Reveal delay={0.18}>
            <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-caption text-muted border-b border-rule pb-4">
              <span>
                {lessons.length} lessons
                {exercises > 0 && ` · ${exercises} graded exercises`}
              </span>
              <span>·</span>
              <span>{module.estimatedHours} hours</span>
              <span>·</span>
              <span className="capitalize">{module.difficulty}</span>

              {module.prerequisites.length > 0 ? (
                <>
                  <span>·</span>
                  <span>
                    <span className="font-medium text-ink-soft">Prerequisite:</span>{' '}
                    {prerequisiteNames(course, module.prerequisites)}
                  </span>
                </>
              ) : (
                <>
                  <span>·</span>
                  <span className="text-ink-soft">No prerequisites</span>
                </>
              )}
            </div>
          </Reveal>

          <RuledList>
            {lessons.map((lesson, index) => (
              <RuledRow
                key={lesson.id}
                index={index}
                aside={String(index + 1).padStart(2, '0')}
                title={lesson.title}
                meta={
                  lesson.exercise
                    ? `${lesson.estimatedMinutes} min · exercise`
                    : `${lesson.estimatedMinutes} min`
                }
                href={`/learn/${course.slug}/${module.slug}/${lesson.slug}`}
              >
                {lesson.summary}
              </RuledRow>
            ))}
          </RuledList>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
