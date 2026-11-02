import Link from 'next/link'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Reveal } from '@/components/reveal'
import { Eyebrow, PullQuote, Rule, RuledList, RuledRow, Wrap } from '@/components/layout'
import { activeCourses, activeModules } from '@/lib/content'

const courses = activeCourses()
const allModules = courses.flatMap(activeModules)
const totalLessons = allModules.reduce((n, m) => n + m.lessons.length, 0)
const totalExercises = allModules.reduce(
  (n, m) => n + m.lessons.filter((l) => l.exercise).length,
  0,
)
const totalHours = Math.round(allModules.reduce((n, m) => n + m.estimatedHours, 0))

export default function LandingPage() {
  return (
    <>
      <SiteHeader />

      <main id="main">
        {/* The hero: clear, direct, and highlighting the full breadth of disciplines */}
        <Wrap className="pt-20 pb-4 sm:pt-28">
          <Reveal variant="settle">
            <h1 className="max-w-[17ch] text-display text-ink">
              Master software systems by{' '}
              <em className="italic text-accent">building them</em>.
            </h1>
          </Reveal>

          <Reveal delay={0.14}>
            <div className="mt-8 max-w-[56ch]">
              <div data-rule className="h-px w-16 origin-left bg-accent" aria-hidden />
              <p className="mt-6 font-serif text-lead text-ink-soft">
                Four rigorous technical tracks: systems programming in C, C++, and Python; data
                engineering; quantitative trading; and AI agent architectures. {totalLessons} lessons
                and {totalExercises} interactive exercises graded on your own machine in sub-second
                timeboxes, with zero external dependencies.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.24}>
            <div className="mt-9 flex flex-wrap items-center gap-x-7 gap-y-3">
              <Link
                href="/signup"
                className="inline-flex min-h-11 items-center rounded-field bg-ink px-6 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
              >
                Choose a track & start
              </Link>
              <Link
                href="/learn"
                className="group inline-flex min-h-11 items-center gap-2 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
              >
                Explore all courses
                <span
                  aria-hidden
                  className="transition-transform duration-200 ease-paper group-hover:translate-x-1.5"
                >
                  &rarr;
                </span>
              </Link>
            </div>
          </Reveal>
        </Wrap>

        {/* The core design invariants */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <h2 className="max-w-[24ch] text-title text-ink">
              Pure standard library. Zero API keys. Instant local grading.
            </h2>
          </Reveal>

          <Reveal delay={0.06}>
            <div className="mt-7 grid gap-x-16 gap-y-6 lg:grid-cols-2">
              <div className="max-w-[58ch] space-y-5 text-ink-soft">
                <p>
                  Every exercise runs in your terminal or browser worker against the pure Python standard
                  library or simulated machine memory. You write the byte allocator, the limit order book,
                  the idempotent pipeline, or the ReAct tool loop.
                </p>
                <p>
                  Tests finish in about a second and give deterministic answers on every run. A failing test
                  is always your own logic to investigate, never a flaky network call, API rate limit, or
                  an external service having an outage. It works offline and on a plane.
                </p>
              </div>

              <div className="max-w-[58ch] space-y-5 text-ink-soft">
                <p>
                  No fluff, no promotional distractions, and no hand-waving abstractions. You implement
                  the underlying mechanisms, data structures, and failure recoveries before relying on
                  frameworks that hide them.
                </p>
                <p>
                  Each exercise opens on a typed scaffold with docstrings. Complete worked reference
                  solutions exist for every challenge and unlock with a confirmed click after your attempt.
                </p>
              </div>
            </div>
          </Reveal>
        </Wrap>

        {/* The 4 Learning Tracks */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <div>
                <Eyebrow>The Catalogue</Eyebrow>
                <h2 className="mt-2 text-title text-ink">Four distinct learning paths</h2>
              </div>
              <span className="text-caption text-muted">
                {courses.length} courses · {allModules.length} modules · ~{totalHours} hours
              </span>
            </div>
          </Reveal>
          <Reveal delay={0.06}>
            <p className="mt-4 max-w-[58ch] font-serif text-lead text-ink-soft">
              Each course is self-contained. Start with low-level systems in C/C++, move into data
              pipelines, model quantitative markets, or orchestrate autonomous AI agent systems.
            </p>
          </Reveal>

          <RuledList>
            {courses.map((course, index) => {
              const modules = activeModules(course)
              const lessonsCount = modules.reduce((n, m) => n + m.lessons.length, 0)
              const exCount = modules.reduce(
                (n, m) => n + m.lessons.filter((l) => l.exercise).length,
                0,
              )
              const hours = Math.round(modules.reduce((n, m) => n + m.estimatedHours, 0))

              return (
                <RuledRow
                  key={course.id}
                  index={index}
                  aside={String(course.order + 1).padStart(2, '0')}
                  title={course.name}
                  meta={`${modules.length} modules · ${lessonsCount} lessons · ${exCount} exercises · ${hours}h`}
                  href={`/learn/${course.slug}`}
                >
                  <p>{course.summary}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {course.tracks.map((t) => (
                      <span
                        key={t.id}
                        className="font-mono text-[11px] uppercase tracking-wider text-muted"
                      >
                        [{t.name}]
                      </span>
                    ))}
                  </div>
                </RuledRow>
              )
            })}
          </RuledList>
        </Wrap>

        {/* Desktop App Integration */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <h2 className="max-w-[20ch] text-title text-ink">
              Read online. <em className="italic text-accent">Practice</em> in the desktop IDE.
            </h2>
          </Reveal>

          <Reveal delay={0.06}>
            <div className="mt-7 max-w-[58ch] space-y-5 text-ink-soft">
              <p>
                The Atlas desktop app places the lesson, a native code editor, and a sandboxed test terminal
                side by side. You write code, run local test suites, and watch results stream in real time.
              </p>
              <p>
                Your progress and awards sync seamlessly between the web reader and the desktop practice
                environment.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.12}>
            <Link
              href="/download"
              className="group mt-8 inline-flex min-h-11 items-center gap-2 text-caption text-accent-deep transition-colors duration-200 ease-paper hover:text-ink"
            >
              Download the desktop app
              <span
                aria-hidden
                className="transition-transform duration-200 ease-paper group-hover:translate-x-1.5"
              >
                &rarr;
              </span>
            </Link>
          </Reveal>
        </Wrap>

        <Wrap className="pb-28">
          <PullQuote>
            &ldquo;Writing the runtime once is what makes every framework readable
            afterwards.&rdquo;
          </PullQuote>
          <Rule className="mt-20" />
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
