import Link from 'next/link'

interface ModuleLike {
  slug: string
  name: string
  order: number
  lessons: { id: string; slug: string; title: string; order: number }[]
}

/**
 * Within-module navigation.
 *
 * Two presentations of the same list. Above `lg` it is a margin column, the way
 * a textbook puts its contents in the margin. Below that the column has nowhere
 * to go, so it becomes a disclosure directly under the masthead. It is never
 * simply hidden: dropping the only structural navigation on small screens
 * leaves a phone reader with prev/next at the bottom of a long article and no
 * sense of where they are.
 */
export function LessonSidebar({
  module,
  activeLessonId,
}: {
  module: ModuleLike
  activeLessonId: string
}) {
  const lessons = [...module.lessons].sort((a, b) => a.order - b.order)
  const position = lessons.findIndex((lesson) => lesson.id === activeLessonId) + 1

  const list = (
    <ol className="space-y-px">
      {lessons.map((lesson, index) => {
        const active = lesson.id === activeLessonId
        return (
          <li key={lesson.id}>
            <Link
              href={`/learn/${module.slug}/${lesson.slug}`}
              aria-current={active ? 'page' : undefined}
              className={`flex min-h-11 items-baseline gap-3 py-2 text-caption transition-colors duration-200 ease-paper ${
                active ? 'text-ink' : 'text-muted hover:text-ink'
              }`}
            >
              <span className="font-mono tabular-nums text-muted">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span className={active ? 'font-medium' : undefined}>{lesson.title}</span>
            </Link>
          </li>
        )
      })}
    </ol>
  )

  return (
    <>
      <aside className="hidden w-56 shrink-0 lg:block">
        <div className="sticky top-24">
          <p className="text-eyebrow font-medium uppercase text-muted">{module.name}</p>
          <div className="mt-4 border-t border-rule pt-2">{list}</div>
        </div>
      </aside>

      <details className="group mb-8 border-b border-rule pb-2 lg:hidden">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-caption text-ink-soft">
          <span className="font-medium text-ink">{module.name}</span>
          <span className="text-muted">
            · {position} of {lessons.length}
          </span>
          <span
            aria-hidden
            className="ml-auto transition-transform duration-200 ease-paper group-open:rotate-180"
          >
            &darr;
          </span>
        </summary>
        <div className="pb-2">{list}</div>
      </details>
    </>
  )
}
