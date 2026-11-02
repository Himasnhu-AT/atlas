import Link from 'next/link'
import type { ReactNode } from 'react'
import { layoutCourse } from '@atlas/core'

import { CurriculumPreview, type CoursePreviewData } from '@/components/curriculum-preview'
import { activeCourses, activeModules } from '@/lib/content'

export default function AuthLayout({ children }: { children: ReactNode }) {
  const rawCourses = activeCourses()
  const coursesData: CoursePreviewData[] = rawCourses.map((course) => {
    const modules = activeModules(course)
    const map = layoutCourse(
      modules.map((m) => ({
        id: m.id,
        slug: m.slug,
        name: m.name,
        order: m.order,
        prerequisites: m.prerequisites,
      })),
    )
    return {
      id: course.id,
      name: course.name,
      slug: course.slug,
      modules: modules.map((m) => ({
        id: m.id,
        name: m.name,
        order: m.order,
        prerequisites: m.prerequisites,
        lessonCount: m.lessons.length,
        sideRoad: map.nodes.find((n) => n.id === m.id)?.sideRoad,
      })),
      map,
    }
  })

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-paper">
      {/* Left 50%: Auth Form */}
      <div className="flex min-h-screen flex-col justify-between p-6 sm:p-10 lg:p-14 xl:p-16">
        <header className="flex items-center justify-between">
          <Link href="/" className="font-serif text-[18px] font-medium tracking-[-0.01em] text-ink">
            Atlas
          </Link>
          <Link
            href="/learn"
            className="text-caption text-ink-soft transition-colors hover:text-ink"
          >
            Explore courses →
          </Link>
        </header>

        <main id="main" className="my-auto flex w-full justify-center py-10">
          <div className="w-full max-w-[24rem]">
            {children}
          </div>
        </main>

        <footer className="text-[12px] text-muted">
          <span>Atlas © {new Date().getFullYear()}</span>
        </footer>
      </div>

      {/* Right 50%: Full Height Curriculum Roadmap */}
      <div className="hidden lg:flex h-screen sticky top-0 border-l border-rule bg-paper-sunken/30 flex-col justify-between p-8 xl:p-12 overflow-hidden">
        <CurriculumPreview courses={coursesData} />
      </div>
    </div>
  )
}
