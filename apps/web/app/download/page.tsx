import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, RuledList, RuledRow, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { latestDesktopRelease, RELEASES_URL, type Installer } from '@/lib/releases'

export const metadata: Metadata = {
  title: 'Desktop app',
  description: 'The practice environment: lesson, editor, and terminal side by side.',
}

const button =
  'inline-flex min-h-11 items-center rounded-field bg-ink px-6 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep'

function megabytes(installer: Installer) {
  return `${Math.round(installer.size / 1_000_000)} MB`
}

export default async function DownloadPage() {
  const release = await latestDesktopRelease()

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
                {release ? `Version ${release.version}` : 'Download'}
              </p>
              {release && (release.mac || release.windows) ? (
                <>
                  <div className="mt-5 flex flex-wrap gap-3">
                    {release.mac && (
                      <a href={release.mac.url} className={button}>
                        macOS, .dmg ({megabytes(release.mac)})
                      </a>
                    )}
                    {release.windows && (
                      <a href={release.windows.url} className={button}>
                        Windows, .{release.windows.name.split('.').pop()} installer ({megabytes(release.windows)})
                      </a>
                    )}
                  </div>
                  <p className="mt-5 max-w-[60ch] text-ink-soft">
                    The macOS app is signed and notarized by Apple and opens like any other. The
                    Windows installer is not code-signed yet, so SmartScreen may stop it the first
                    time: choose More info, then Run anyway. It then installs like any app and
                    shows up in Start and in Installed apps.
                  </p>
                  <p className="mt-3 text-ink-soft">
                    <a href={release.url} className="underline underline-offset-4 hover:text-accent-deep">
                      Release notes and other files
                    </a>
                  </p>
                </>
              ) : (
                <p className="mt-3 max-w-[54ch] text-ink-soft">
                  No installer is published yet. Check the{' '}
                  <a href={RELEASES_URL} className="underline underline-offset-4 hover:text-accent-deep">
                    releases page
                  </a>
                  , or build it from source below.
                </p>
              )}

              <p className="mt-10 text-eyebrow font-medium uppercase text-muted">
                Or build it from source
              </p>
              <pre className="mt-4 overflow-x-auto rounded-sheet border border-rule bg-paper-raised p-5 text-[13px] leading-relaxed">
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
