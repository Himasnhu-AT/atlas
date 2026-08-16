import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeModules, findModule } from '@/lib/content'

export function generateStaticParams() {
  return activeModules().map((module) => ({ moduleSlug: module.slug }))
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ moduleSlug: string }>
}): Promise<Metadata> {
  const module = findModule((await params).moduleSlug)
  return module ? { title: module.name, description: module.summary } : {}
}

export default async function ModulePage({
  params,
}: {
  params: Promise<{ moduleSlug: string }>
}) {
  const { moduleSlug } = await params
  const module = findModule(moduleSlug)
  if (!module) notFound()

  const lessons = [...module.lessons].sort((a, b) => a.order - b.order)
  const exercises = lessons.filter((lesson) => lesson.exercise).length

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <Reveal>
            <Link
              href="/learn"
              className="group inline-flex min-h-11 items-center gap-2 text-caption text-muted transition-colors duration-200 ease-paper hover:text-ink"
            >
              <span
                aria-hidden
                className="transition-transform duration-200 ease-paper group-hover:-translate-x-1"
              >
                &larr;
              </span>
              Curriculum
            </Link>
          </Reveal>

          <div className="mt-4">
            <PageHeader
              eyebrow={`Module ${String(module.order).padStart(2, '0')}`}
              title={module.name}
              lead={module.summary}
            />
          </div>

          <Reveal delay={0.18}>
            <p className="mt-6 text-caption text-muted">
              {lessons.length} lessons
              {exercises > 0 && ` · ${exercises} graded exercises`} · about{' '}
              {module.estimatedHours} hours · {module.difficulty}
            </p>
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
                href={`/learn/${module.slug}/${lesson.slug}`}
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
