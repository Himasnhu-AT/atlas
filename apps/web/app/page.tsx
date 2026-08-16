import Link from 'next/link'
import manifest from '@learn/learning/manifest'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Reveal } from '@/components/reveal'
import { PullQuote, Rule, RuledList, RuledRow, Wrap } from '@/components/layout'

const modules = [...manifest.modules].sort((a, b) => a.order - b.order)
const exerciseCount = modules.reduce(
  (n, m) => n + m.lessons.filter((l) => l.exercise).length,
  0,
)

export default function LandingPage() {
  return (
    <>
      <SiteHeader />

      <main id="main">
        {/* The hero is a page opening, not a marketing block: a label, a
            sentence someone would actually say, and two ways in. */}
        <Wrap className="pt-20 pb-4 sm:pt-28">
          <Reveal variant="settle">
            <h1 className="max-w-[15ch] text-display text-ink">
              Learn to build agents by{' '}
              <em className="italic text-accent">building them</em>.
            </h1>
          </Reveal>

          <Reveal delay={0.14}>
            <div className="mt-8 max-w-[54ch]">
              <div data-rule className="h-px w-16 origin-left bg-accent" aria-hidden />
              <p className="mt-6 font-serif text-lead text-ink-soft">
                Eleven modules that end in code you run. You write the tool-calling loop, the
                retrieval pipeline, the state graph a framework would have handed you. Tests
                tell you whether it works, in about a second, without an API key.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.24}>
            <div className="mt-9 flex flex-wrap items-center gap-x-7 gap-y-3">
              <Link
                href="/signup"
                className="inline-flex min-h-11 items-center rounded-field bg-ink px-6 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep"
              >
                Start module 0
              </Link>
              <Link
                href="/learn"
                className="group inline-flex min-h-11 items-center gap-2 text-caption text-ink-soft transition-colors duration-200 ease-paper hover:text-ink"
              >
                Read the curriculum
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

        {/* The premise. Prose rather than a grid of four equal claims, because
            the argument has an order and a card grid destroys order. */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <h2 className="max-w-[22ch] text-title text-ink">
              Nothing here calls a real model
            </h2>
          </Reveal>

          <Reveal delay={0.06}>
            <div className="mt-7 grid gap-x-16 gap-y-6 lg:grid-cols-2">
              <div className="max-w-[58ch] space-y-5 text-ink-soft">
                <p>
                  Every exercise runs against a scripted client with the same shape as a
                  provider SDK. The same response objects, the same{' '}
                  <code className="rounded-[3px] bg-paper-sunken px-1.5 py-0.5 text-[0.88em] text-ink">
                    finish_reason
                  </code>
                  , the same tool-call structure. What is missing is the network request.
                </p>
                <p>
                  So tests finish in about a second and give the same answer every run. A red
                  test is your bug, never a model having an off day. There is no key to get, no
                  bill, and no rate limit between you and lesson one. It works on a plane.
                </p>
              </div>

              <div className="max-w-[58ch] space-y-5 text-ink-soft">
                <p>
                  The tradeoff is real and worth saying plainly: you will not watch a live model
                  surprise you, and that is a genuine part of the craft.
                </p>
                <p>
                  It is also what the provider modules exist for later. Because the mock mirrors
                  the SDK shape, the loop you write here is the loop you would write against a
                  real provider. Swapping the client is one line.
                </p>
              </div>
            </div>
          </Reveal>
        </Wrap>

        {/* The curriculum. Numerals earn their place: they are the order you
            take the modules in, not decoration. */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <h2 className="text-title text-ink">The curriculum</h2>
          </Reveal>
          <Reveal delay={0.06}>
            <p className="mt-4 max-w-[54ch] font-serif text-lead text-ink-soft">
              From what a model actually does, to routing work across specialists.{' '}
              {exerciseCount} exercises, each graded on your own machine.
            </p>
          </Reveal>

          <RuledList>
            {modules.map((module, index) => (
              <RuledRow
                key={module.id}
                index={index}
                aside={String(module.order).padStart(2, '0')}
                title={module.name}
                meta={`${module.lessons.length} lessons · ${module.estimatedHours}h`}
                href={`/learn/${module.slug}`}
              >
                {module.summary}
              </RuledRow>
            ))}
          </RuledList>
        </Wrap>

        {/* Practice. */}
        <Wrap className="pt-24 sm:pt-32">
          <Reveal>
            <h2 className="max-w-[20ch] text-title text-ink">
              Read here. <em className="italic text-accent">Practice</em> in the desktop app.
            </h2>
          </Reveal>

          <Reveal delay={0.06}>
            <div className="mt-7 max-w-[58ch] space-y-5 text-ink-soft">
              <p>
                The desktop app puts the lesson, a real editor, and a real terminal side by
                side. You write, you run, you watch the tests go green. Progress follows you
                between the two.
              </p>
              <p>
                Each exercise opens on a scaffold: signatures and docstrings with empty bodies.
                A complete reference solution exists and it takes a deliberate click to see.
                Reading a working solution after a real attempt teaches you something. Reading
                one instead of attempting does not.
              </p>
            </div>
          </Reveal>

          <Reveal delay={0.12}>
            <Link
              href="/download"
              className="group mt-8 inline-flex min-h-11 items-center gap-2 text-caption text-accent-deep transition-colors duration-200 ease-paper hover:text-ink"
            >
              Get the desktop app
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
            &ldquo;Writing the loop once is what makes every framework readable
            afterwards.&rdquo;
          </PullQuote>
          <Rule className="mt-20" />
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
