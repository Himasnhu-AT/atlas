import Link from 'next/link'
import type { Metadata } from 'next'
import { layoutCourse, type CourseMap, type MapNode } from '@atlas/core'
import { WaxSeal } from '@atlas/ui/game'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Eyebrow, PageHeader, PullQuote, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeCourses, activeModules } from '@/lib/content'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

export const metadata: Metadata = {
  title: 'Atlas',
  description: 'Every course as a chart: what leads where, and what is optional.',
}

/** Geometry, in the SVG's own units. */
const COL = 300
const ROW = 104
const PAD_X = 18
const PAD_Y = 26
/** Room for the longest label in the rightmost column, which has no next column. */
const LABEL = 290

function x(col: number) {
  return PAD_X + col * COL
}
function y(row: number) {
  return PAD_Y + row * ROW
}

/**
 * An edge, drawn as a line that leaves straight down and arrives straight down.
 *
 * A branch bends once in the middle rather than running diagonally, because a
 * diagonal across a chart reads as a relationship of a different kind, and every
 * edge here means the same thing.
 */
function edgePath(from: MapNode, to: MapNode): string {
  const x1 = x(from.col)
  const y1 = y(from.row) + 12
  const x2 = x(to.col)
  const y2 = y(to.row) - 12

  if (x1 === x2) return `M ${x1} ${y1} L ${x2} ${y2}`

  const mid = (y1 + y2) / 2
  return `M ${x1} ${y1} L ${x1} ${mid - 14} Q ${x1} ${mid} ${x1 + Math.sign(x2 - x1) * 14} ${mid} L ${x2 - Math.sign(x2 - x1) * 14} ${mid} Q ${x2} ${mid} ${x2} ${mid + 14} L ${x2} ${y2}`
}

export default async function AtlasPage() {
  const user = await currentUser()
  const snapshot = user ? await store().progressFor(user.id) : null

  const completedModules = new Set(
    (snapshot?.modules ?? []).filter((m) => m.status === 'completed').map((m) => m.moduleId),
  )
  const completedLessons = new Set(
    (snapshot?.lessons ?? []).filter((l) => l.status === 'completed').map((l) => l.lessonId),
  )

  const courses = activeCourses()

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="The atlas"
            title={
              <>
                What leads <em className="italic text-accent">where</em>
              </>
            }
            lead="Each course is a chart. A line means one module assumes the one above it, and a side road is a branch the course never asks you to come back from."
          />

          {courses.map((course) => {
            const modules = activeModules(course)
            const map: CourseMap = layoutCourse(
              modules.map((m) => ({
                id: m.id,
                slug: m.slug,
                name: m.name,
                order: m.order,
                prerequisites: m.prerequisites,
              })),
            )
            const byId = new Map(map.nodes.map((n) => [n.id, n]))

            return (
              <section key={course.id} className="mt-20 first:mt-16">
                <Reveal>
                  <Eyebrow>{course.name}</Eyebrow>
                </Reveal>

                {/* The chart can be wider than a phone, so it scrolls inside its
                    own box rather than making the page scroll sideways. */}
                <div className="mt-8 -mx-6 overflow-x-auto px-6 sm:mx-0 sm:px-0">
                  <svg
                    viewBox={`0 0 ${PAD_X * 2 + (map.cols - 1) * COL + LABEL} ${PAD_Y * 2 + (map.rows - 1) * ROW}`}
                    width={PAD_X * 2 + (map.cols - 1) * COL + LABEL}
                    className="max-w-none"
                    role="img"
                    aria-label={`${course.name}: ${map.nodes.length} modules and what each one assumes`}
                  >
                    {map.edges.map((edge) => {
                      const from = byId.get(edge.from)
                      const to = byId.get(edge.to)
                      if (!from || !to) return null
                      const travelled = completedModules.has(edge.from)
                      return (
                        <path
                          key={`${edge.from}-${edge.to}`}
                          d={edgePath(from, to)}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={1}
                          className={travelled ? 'text-accent' : 'text-rule-strong'}
                        />
                      )
                    })}

                    {map.nodes.map((node) => {
                      const module = modules.find((m) => m.id === node.id)!
                      const done = completedModules.has(node.id)
                      const unlocked = node.prerequisites.every((id) => completedModules.has(id))
                      const started = module.lessons.some((l) => completedLessons.has(l.id))

                      return (
                        <g key={node.id}>
                          <circle
                            cx={x(node.col)}
                            cy={y(node.row)}
                            r={5}
                            fill={done || started ? 'currentColor' : 'var(--color-paper)'}
                            stroke="currentColor"
                            strokeWidth={1}
                            className={
                              done ? 'text-accent' : unlocked ? 'text-ink-soft' : 'text-rule-strong'
                            }
                          />
                          <text
                            x={x(node.col) + 14}
                            y={y(node.row)}
                            dominantBaseline="central"
                            fontSize="13"
                            fontFamily="var(--font-sans)"
                            fill="currentColor"
                            className={
                              done ? 'text-ink' : unlocked ? 'text-ink-soft' : 'text-muted'
                            }
                          >
                            {node.name}
                          </text>
                          <text
                            x={x(node.col) + 14}
                            y={y(node.row) + 17}
                            dominantBaseline="central"
                            fontSize="11"
                            fontFamily="var(--font-mono)"
                            fill="currentColor"
                            className="text-muted"
                          >
                            {module.lessons.filter((l) => completedLessons.has(l.id)).length} /{' '}
                            {module.lessons.length}
                            {node.sideRoad ? ' · side road' : ''}
                          </text>
                        </g>
                      )
                    })}
                  </svg>
                </div>

                {/* The chart is a picture, so it carries one description and
                    nothing inside it is focusable. This is the navigation. */}
                <h3 className="mt-10 text-eyebrow font-medium uppercase text-muted">
                  Open a module
                </h3>
                <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-3">
                  {modules.map((module) => {
                    const done = completedModules.has(module.id)
                    return (
                      <li key={module.id}>
                        <Link
                          href={`/learn/${course.slug}/${module.slug}`}
                          className="inline-flex min-h-11 items-center gap-2 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
                        >
                          <span className={done ? 'text-accent' : 'text-rule-strong'}>
                            <WaxSeal earned={done} />
                          </span>
                          {module.name}
                        </Link>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )
          })}

          <PullQuote>
            &ldquo;A branch with nothing below it is not a detour. It is a road that happens to
            end where you stop.&rdquo;
          </PullQuote>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
