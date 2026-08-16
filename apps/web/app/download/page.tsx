import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'

export const metadata: Metadata = {
  title: 'Desktop app',
  description: 'The practice environment: lesson, editor, and terminal side by side.',
}

export default function DownloadPage() {
  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="Practice"
            title={
              <>
                The <em className="italic text-accent">workbench</em>
              </>
            }
            lead="Three panes: the lesson, a real editor, and a real terminal. Write your solution, run the tests, and watch them go green without leaving the window."
          />

          <Reveal delay={0.2}>
            <div className="mt-14 border-t-2 border-ink pt-7">
              <p className="text-eyebrow font-medium uppercase text-muted">
                Build it from source
              </p>
              <p className="mt-3 max-w-[54ch] text-ink-soft">
                Signed installers are not published yet. The app builds and runs locally today.
              </p>
              <pre className="mt-6 overflow-x-auto rounded-sheet border border-rule bg-paper-raised p-5 text-[13px] leading-relaxed">
                <code>{`pnpm install
pnpm content
pnpm dev:desktop`}</code>
              </pre>
            </div>
          </Reveal>

          <RuledList>
            <RuledRow index={0} aside="01" title="What you need">
              <p>
                Python 3.10 or newer, to run the exercise tests. Rust and a platform toolchain
                only if you are building the app yourself.
              </p>
              <p className="mt-3">
                Nothing else. No API key, no virtual environment, no local model. The app checks
                your setup on first launch and tells you exactly what is missing rather than
                failing at the moment you press Run.
              </p>
            </RuledRow>

            <RuledRow index={1} aside="02" title="How exercises open">
              <p>
                On a scaffold: function signatures and docstrings with empty bodies. A complete
                reference solution ships beside it, and the app will not show it unless you ask.
              </p>
              <p className="mt-3">
                Reading a working solution after a genuine attempt teaches you something.
                Reading one instead of attempting does not, which is why it takes a deliberate
                click and gets recorded when it happens.
              </p>
            </RuledRow>

            <RuledRow index={2} aside="03" title="Where your work lives">
              <p>
                In a sandboxed workspace on your own machine, saved as you type. Your code and
                your progress sync with this site, so you can read a chapter on a phone and
                write the exercise on a laptop.
              </p>
            </RuledRow>
          </RuledList>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
