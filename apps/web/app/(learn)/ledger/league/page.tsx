import Link from 'next/link'
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'
import { isoWeekOf, levelForXp } from '@atlas/core'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { PageHeader, Rule, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { LeaderboardOptIn } from '@/components/leaderboard-opt-in'
import { currentUser } from '@/lib/server/session'
import { store } from '@/lib/server/store'
import { serverDay, weekStart } from '@/lib/server/xp'

export const metadata: Metadata = { title: 'The week' }

const LEAGUE_SIZE = 30

/**
 * The week's board.
 *
 * Opt-in, off by default, and small on purpose. A global ranking is motivating
 * for the top of it and discouraging for everyone else, which is the wrong trade
 * for a learning tool: the people most likely to stop are the ones a public
 * ranking tells they are behind.
 *
 * No medals, no podium, no highlight on first place. Ruled rows, in order.
 */
export default async function LeaguePage() {
  const user = await currentUser()
  if (!user) redirect('/login?next=/ledger/league')

  const game = await store().gameFor(user.id)

  if (!game.leaderboardOptIn) {
    return (
      <>
        <SiteHeader />
        <main id="main" className="pt-20 pb-28 sm:pt-24">
          <Wrap>
            <PageHeader
              eyebrow="The week"
              title={
                <>
                  Not on the <em className="italic text-accent">board</em>
                </>
              }
              lead="The board is off unless you ask for it. Nobody can see your name on a ranking you did not join, and turning it off again takes one click."
            />
            <Reveal delay={0.2}>
              <div className="mt-12">
                <LeaderboardOptIn optedIn={false} />
              </div>
            </Reveal>
          </Wrap>
        </main>
        <SiteFooter />
      </>
    )
  }

  const rows = await store().weeklyLeaderboard(weekStart(), LEAGUE_SIZE)

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow={isoWeekOf(serverDay())}
            title={
              <>
                This <em className="italic text-accent">week</em>
              </>
            }
            lead="XP earned since Monday, among the people who joined. It resets on Monday and nothing is carried over."
          />

          <div className="mt-12">
            <Rule />
            {rows.map((row, index) => {
              const you = row.userId === user.id
              return (
                <Reveal key={row.userId} delay={Math.min(index, 3) * 0.05}>
                  <div
                    className={`grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-x-4 border-b border-rule py-5 ${
                      you ? 'bg-paper-raised' : ''
                    }`}
                  >
                    <span className="font-mono text-caption tabular-nums text-muted">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className={you ? 'text-ink' : 'text-ink-soft'}>
                      {row.displayName}
                      {you && <span className="ml-2 text-caption text-muted">you</span>}
                    </span>
                    <span className="font-mono text-caption tabular-nums text-muted">
                      lvl {levelForXp(row.totalXp)} · {row.weeklyXp} xp
                    </span>
                  </div>
                </Reveal>
              )
            })}

            {rows.length === 0 && (
              <p className="py-8 text-ink-soft">
                Nobody has earned anything yet this week. That includes you.
              </p>
            )}
          </div>

          <Reveal>
            <div className="mt-16">
              <LeaderboardOptIn optedIn />
            </div>
          </Reveal>

          <Reveal>
            <p className="mt-10 max-w-[56ch] text-caption text-muted">
              Grading happens on your own machine, so this board runs on trust. It is opt-in
              and it is thirty people, which is about as much as that is worth.{' '}
              <Link href="/ledger" className="text-accent-deep underline underline-offset-2">
                Your ledger
              </Link>{' '}
              is the number that matters.
            </p>
          </Reveal>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
