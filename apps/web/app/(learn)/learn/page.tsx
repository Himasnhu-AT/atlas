import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Eyebrow, PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { activeModules, prerequisiteNames } from '@/lib/content'

export const metadata: Metadata = {
  title: 'Curriculum',
  description:
    'Eleven modules, from what a language model does to a project you could put in front of someone.',
}

const TRACKS: Record<string, { label: string; note: string }> = {
  base: {
    label: 'Shared base',
    note: 'Everyone starts here, whatever you build afterwards.',
  },
  agent: {
    label: 'Agent track',
    note: 'Where you build the thing: tools, loops, retrieval, orchestration.',
  },
  cli: { label: 'CLI track', note: 'Working with agents from the terminal.' },
  frameworks: {
    label: 'Understanding frameworks',
    note: 'Rebuild what LangGraph, CrewAI and the Agents SDK do, small enough to hold in your head.',
  },
  projects: {
    label: 'Real-life projects',
    note: 'End to end builds, the kind you would actually put in front of someone.',
  },
}

export default function CatalogPage() {
  const modules = activeModules()
  const tracks = [...new Set(modules.map((module) => module.track))]

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
            lead="Start at module 0 and work down. Everything after the shared base assumes the modules before it, and the app enforces that."
          />

          {tracks.map((track) => {
            const meta = TRACKS[track] ?? { label: track, note: '' }
            return (
              <section key={track} className="mt-20 first:mt-16">
                <Reveal>
                  <Eyebrow>{meta.label}</Eyebrow>
                  {meta.note && (
                    <p className="mt-3 max-w-[52ch] text-ink-soft">{meta.note}</p>
                  )}
                </Reveal>

                <RuledList>
                  {modules
                    .filter((module) => module.track === track)
                    .map((module, index) => (
                      <RuledRow
                        key={module.id}
                        index={index}
                        aside={String(module.order).padStart(2, '0')}
                        title={module.name}
                        meta={`${module.lessons.length} lessons · ${module.estimatedHours}h · ${module.difficulty}`}
                        href={`/learn/${module.slug}`}
                      >
                        <p>{module.summary}</p>
                        {module.prerequisites.length > 0 && (
                          <p className="mt-2 text-caption text-muted">
                            After {prerequisiteNames(module.prerequisites)}
                          </p>
                        )}
                      </RuledRow>
                    ))}
                </RuledList>
              </section>
            )
          })}
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
