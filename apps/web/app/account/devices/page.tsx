import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, Rule, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { RevokeDevice } from '@/components/revoke-device'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'

export const metadata: Metadata = { title: 'Devices' }

function ago(iso: string): string {
  const minutes = Math.floor((Date.now() - Date.parse(iso)) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  return `${Math.floor(hours / 24)} days ago`
}

/**
 * Devices connected to this account.
 *
 * Revocation has to be reachable by a person, or it is a capability the API has
 * and the product does not.
 */
export default async function DevicesPage() {
  const user = await currentUser()
  if (!user) redirect('/login?next=/account/devices')

  const devices = (await store().devicesFor(user.id)).filter((d) => !d.revokedAt)

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="Your account"
            title={
              <>
                Connected <em className="italic text-accent">devices</em>
              </>
            }
            lead="Practice apps that can sync progress to this account. Disconnecting one takes effect immediately, and it can be connected again from the app."
          />

          <div className="mt-12">
            <Rule />
            {devices.map((device) => (
              <Reveal key={device.id}>
                <div className="flex flex-wrap items-baseline gap-x-6 gap-y-3 border-b border-rule py-7">
                  <div className="min-w-0 flex-1">
                    <p className="text-section text-ink">{device.name}</p>
                    <p className="mt-1 text-caption text-muted">
                      {device.platform} · {device.appVersion} · last synced {ago(device.lastSeenAt)}
                    </p>
                  </div>
                  <RevokeDevice deviceId={device.id} name={device.name} />
                </div>
              </Reveal>
            ))}

            {devices.length === 0 && (
              <p className="py-8 max-w-[56ch] text-ink-soft">
                No devices connected. The practice app offers to connect one the first time you
                open it with an account.
              </p>
            )}
          </div>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
