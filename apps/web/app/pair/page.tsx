import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { PairForm } from '@/components/pair-form'
import { currentUser } from '@/lib/server/session'

export const metadata: Metadata = { title: 'Connect a device' }

export default async function PairPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>
}) {
  const { code } = await searchParams
  const user = await currentUser()

  // Sign in first, then come straight back with the code intact. Losing the
  // code at the sign-in step would send the person back to the app to start
  // over, which is where this flow is most likely to lose people.
  if (!user) {
    const next = code ? `/pair?code=${encodeURIComponent(code)}` : '/pair'
    redirect(`/login?next=${encodeURIComponent(next)}`)
  }

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="Connect a device"
            title={
              <>
                Let the app <em className="italic text-accent">in</em>
              </>
            }
            lead="The practice app is showing a code. Type it here and it can sync your progress to this account. You can disconnect it again at any time."
          />

          <Reveal delay={0.2}>
            <div className="mt-12">
              <PairForm initialCode={code ?? ''} />
            </div>
          </Reveal>

          <Reveal delay={0.3}>
            <p className="mt-12 max-w-[56ch] text-caption text-muted">
              If you did not just start this on your own machine, do not enter a code somebody
              sent you. Approving one connects that device to this account.
            </p>
          </Reveal>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
