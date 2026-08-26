'use client'

import { useEffect, useState } from 'react'
import type { CourseMap, MapNode } from '@atlas/core'

export interface CoursePreviewData {
  id: string
  name: string
  slug: string
  modules: {
    id: string
    name: string
    order: number
    prerequisites: string[]
    lessonCount: number
    sideRoad?: boolean
  }[]
  map: CourseMap
}

const COL = 310
const ROW = 66
const PAD_X = 18
const PAD_Y = 22
const LABEL_WIDTH = 480

function x(col: number) {
  return PAD_X + col * COL
}
function y(row: number) {
  return PAD_Y + row * ROW
}

function edgePath(from: MapNode, to: MapNode): string {
  const x1 = x(from.col)
  const y1 = y(from.row) + 9
  const x2 = x(to.col)
  const y2 = y(to.row) - 9

  if (x1 === x2) return `M ${x1} ${y1} L ${x2} ${y2}`

  const mid = (y1 + y2) / 2
  return `M ${x1} ${y1} L ${x1} ${mid - 9} Q ${x1} ${mid} ${x1 + Math.sign(x2 - x1) * 9} ${mid} L ${x2 - Math.sign(x2 - x1) * 9} ${mid} Q ${x2} ${mid} ${x2} ${mid + 9} L ${x2} ${y2}`
}

const AUTO_ROTATE_INTERVAL_MS = 4500

export function CurriculumPreview({ courses }: { courses: CoursePreviewData[] }) {
  const [activeCourseId, setActiveCourseId] = useState(courses[0]?.id ?? '')
  const [isPaused, setIsPaused] = useState(false)

  // Auto-switch between curriculums every 4.5s
  useEffect(() => {
    if (isPaused || courses.length <= 1) return

    const timer = setInterval(() => {
      setActiveCourseId((prev) => {
        const index = courses.findIndex((c) => c.id === prev)
        const nextIndex = (index + 1) % courses.length
        return courses[nextIndex].id
      })
    }, AUTO_ROTATE_INTERVAL_MS)

    return () => clearInterval(timer)
  }, [isPaused, courses])

  const currentCourse = courses.find((c) => c.id === activeCourseId) ?? courses[0]
  if (!currentCourse) return null

  const map = currentCourse.map
  const byId = new Map(map.nodes.map((n) => [n.id, n]))
  const totalLessons = currentCourse.modules.reduce((sum, m) => sum + m.lessonCount, 0)

  const svgWidth = PAD_X * 2 + (map.cols - 1) * COL + LABEL_WIDTH
  const svgHeight = PAD_Y * 2 + (map.rows - 1) * ROW

  return (
    <div
      className="flex h-full flex-col justify-between"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      <div>
        {/* Header telemetry */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-eyebrow font-medium uppercase tracking-wider text-muted">
            <span className="inline-block size-2 rounded-full bg-accent animate-pulse" />
            <span>Curriculum Roadmap</span>
          </div>
          <span className="font-mono text-[12px] text-muted">
            {currentCourse.modules.length} modules · {totalLessons} lessons
          </span>
        </div>

        {/* Course Switcher Pills */}
        <div className="mt-5 flex flex-wrap gap-2">
          {courses.map((course) => {
            const active = course.id === currentCourse.id
            return (
              <button
                key={course.id}
                type="button"
                onClick={() => {
                  setActiveCourseId(course.id)
                  setIsPaused(true)
                }}
                className={`relative rounded-field px-3 py-1.5 text-[12px] font-medium transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-ink ${
                  active
                    ? 'bg-ink text-paper shadow-sm'
                    : 'border border-rule bg-paper/60 text-ink-soft hover:border-rule-strong hover:bg-paper hover:text-ink'
                }`}
              >
                {course.name}
                {active && !isPaused && (
                  <span
                    className="absolute inset-x-1 bottom-0 h-0.5 rounded-full bg-accent animate-pulse"
                    aria-hidden
                  />
                )}
              </button>
            )
          })}
        </div>

        {/* Full-bleed SVG Roadmap Canvas */}
        <div className="mt-8 overflow-x-auto overflow-y-auto max-h-[calc(100vh-280px)] pr-4 scrollbar-thin">
          <div key={currentCourse.id} className="transition-opacity duration-300 ease-in-out">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              width={svgWidth}
              height={svgHeight}
              className="h-auto max-w-none"
              role="img"
              aria-label={`${currentCourse.name} learning roadmap`}
            >
              {map.edges.map((edge) => {
                const from = byId.get(edge.from)
                const to = byId.get(edge.to)
                if (!from || !to) return null
                return (
                  <path
                    key={`${edge.from}-${edge.to}`}
                    d={edgePath(from, to)}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.25}
                    className="text-rule-strong"
                  />
                )
              })}

              {map.nodes.map((node) => {
                const mod = currentCourse.modules.find((m) => m.id === node.id)
                const lessonCount = mod?.lessonCount ?? 0

                return (
                  <g key={node.id} className="group cursor-default">
                    <circle
                      cx={x(node.col)}
                      cy={y(node.row)}
                      r={4.5}
                      fill="var(--color-paper)"
                      stroke="currentColor"
                      strokeWidth={1.5}
                      className="text-ink-soft transition-colors group-hover:text-accent"
                    />
                    <text
                      x={x(node.col) + 14}
                      y={y(node.row) - 3}
                      dominantBaseline="central"
                      fontSize="13"
                      fontFamily="var(--font-sans)"
                      fontWeight="500"
                      fill="currentColor"
                      className="text-ink transition-colors group-hover:text-accent"
                    >
                      {node.name}
                    </text>
                    <text
                      x={x(node.col) + 14}
                      y={y(node.row) + 12}
                      dominantBaseline="central"
                      fontSize="10.5"
                      fontFamily="var(--font-mono)"
                      fill="currentColor"
                      className="text-muted"
                    >
                      0 / {lessonCount}
                      {node.sideRoad ? ' · side road' : ''}
                    </text>
                  </g>
                )
              })}
            </svg>
          </div>
        </div>
      </div>

      {/* Subtle Footer */}
      <div className="mt-6 flex items-center justify-between border-t border-rule pt-4 text-[12px] text-muted">
        <span>Standard library · Code-first mastery</span>
        <span className="font-mono">{isPaused ? 'Paused' : 'Auto-advancing'}</span>
      </div>
    </div>
  )
}
