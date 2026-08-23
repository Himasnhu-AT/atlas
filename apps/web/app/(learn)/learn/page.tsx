import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { activeCourses, activeModules } from '@/lib/content'

export const metadata: Metadata = {
  title: 'Courses',
  description: 'Every course on Atlas, and what each one asks you to build.',
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
                Pick a <em className="italic text-accent">course</em>
              </>
            }
            lead="Each one is self contained. Nothing in a course depends on having finished another, so start with whichever you actually want."
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

              return (
                <RuledRow
                  key={course.id}
                  index={index}
                  aside={String(course.order + 1).padStart(2, '0')}
                  title={course.name}
                  meta={`${modules.length} modules · ${lessons} lessons · ${exercises} exercises · ${Math.round(hours)}h`}
                  href={`/learn/${course.slug}`}
                >
                  <p>{course.summary}</p>
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
