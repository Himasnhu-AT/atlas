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

  // Tracks come from the course's own `course.yaml`. They used to be a hardcoded
  // map in this file, which is why every course would otherwise have had to
  // describe itself in the AI course's vocabulary.
  const tracks = course.tracks.filter((track) =>
    modules.some((module) => module.track === track.id),
  )

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="What you will build"
            title={
              <>
                The <em className="italic text-accent">curriculum</em>
              </>
            }
            lead={course.summary}
          />

          {tracks.map((track) => (
            <section key={track.id} className="mt-20 first:mt-16">
              <Reveal>
                <Eyebrow>{track.name}</Eyebrow>
                {track.note && <p className="mt-3 max-w-[52ch] text-ink-soft">{track.note}</p>}
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
                      <p>{module.summary}</p>
                      {module.prerequisites.length > 0 && (
                        <p className="mt-2 text-caption text-muted">
                          After {prerequisiteNames(course, module.prerequisites)}
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
