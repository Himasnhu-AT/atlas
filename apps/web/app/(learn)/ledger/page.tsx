import Link from 'next/link'
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { RankStamp, RuleMeter, WaxSeal, WeekDots } from '@atlas/ui/game'

import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { Eyebrow, PageHeader, Rule, Wrap } from '@/components/layout'
import { Reveal } from '@/components/reveal'
import { QuestList } from '@/components/quest-list'
import { WeeklyTargetPicker } from '@/components/weekly-target'
import { activeCourses } from '@/lib/content'
import { currentUser } from '@/lib/server/session'
import { gameStateFor } from '@/lib/server/xp'

export const metadata: Metadata = { title: 'Ledger' }

/**
 * The character sheet, set as a ledger page rather than a dashboard.
 *
 * Everything here is a ruled row or a hairline. There is no card, no tile and no
 * ring, because DESIGN.md's one rule outranks the fact that this is the page
 * where a dashboard would be most tempting.
 */
export default async function LedgerPage() {
  const user = await currentUser()
  if (!user) redirect('/login?next=/ledger')

  const game = await gameStateFor(user.id)
  const courses = activeCourses()
  const byId = new Map(courses.map((c) => [c.id, c]))

  const earned = game.seals.filter((s) => s.earnedAt)
  const blank = game.seals.filter((s) => !s.earnedAt)

  return (
    <>
      <SiteHeader />

      <main id="main" className="pt-20 pb-28 sm:pt-24">
        <Wrap>
          <PageHeader
            eyebrow="Your ledger"
            title={
              <>
                Rank {game.level.rank.roman},{' '}
                <em className="italic text-accent">{game.level.rank.name}</em>
              </>
            }
            lead={`Level ${game.level.level}. ${game.level.toNextLevel} to the next.`}
          />

          <Reveal delay={0.2}>
            <div className="mt-12 flex items-center gap-8">
              <span className="shrink-0 text-accent">
                <RankStamp roman={game.level.rank.roman} title={`Rank ${game.level.rank.roman}, ${game.level.rank.name}`} />
              </span>

              <div className="min-w-0 flex-1">
                <p className="flex items-baseline justify-between gap-4 font-mono text-caption tabular-nums text-muted">
                  <span>{game.level.totalXp} xp</span>
                  <span>
                    {game.level.intoLevel} / {game.level.levelSpan} to level {game.level.level + 1}
                  </span>
                </p>
                <RuleMeter
                  className="mt-3"
                  fraction={game.level.levelSpan === 0 ? 0 : game.level.intoLevel / game.level.levelSpan}
                  label={`Level ${game.level.level}, ${game.level.intoLevel} of ${game.level.levelSpan} XP`}
                />
              </div>
            </div>
          </Reveal>

          <section className="mt-20">
            <Reveal>
              <Eyebrow>This week</Eyebrow>
            </Reveal>
            <Reveal delay={0.06}>
              <div className="mt-4 flex flex-wrap items-baseline gap-x-6 gap-y-3">
                <WeekDots daysActive={game.week.daysActive} target={game.week.target} />
                <p className="text-ink-soft">
                  {game.week.daysActive} of {game.week.target} days
                  {game.week.met && <span className="text-pass"> · met</span>}
                </p>
                {game.week.weeksInARow > 0 && (
                  <p className="text-caption text-muted">
                    {game.week.weeksInARow} week{game.week.weeksInARow === 1 ? '' : 's'} running
                  </p>
                )}
              </div>
            </Reveal>
            <Reveal delay={0.12}>
              <div className="mt-6">
                <WeeklyTargetPicker target={game.week.target} chosen={game.week.chosen} />
              </div>
            </Reveal>

            <Reveal delay={0.18}>
              <p className="mt-6 text-caption text-muted">
                <Link
                  href="/ledger/league"
                  className="text-accent-deep underline underline-offset-2"
                >
                  {game.leaderboardOptIn ? "This week's board" : 'There is a weekly board'}
                </Link>{' '}
                {game.leaderboardOptIn
                  ? '· thirty people, resets on Monday.'
                  : '· off unless you join it.'}
              </p>
            </Reveal>
          </section>

          <section className="mt-20">
            <Reveal>
              <Eyebrow>Today</Eyebrow>
            </Reveal>
            <QuestList quests={game.quests} />
          </section>

          <section className="mt-20">
            <Reveal>
              <Eyebrow>
                Seals · {earned.length} of {game.seals.length}
              </Eyebrow>
            </Reveal>

            {/* Deliberately tighter than a `RuledRow`. Fourteen of those is a
                page of its own for the least urgent thing here, and the mark
                belongs beside the name rather than out in the numeral column. */}
            <div className="mt-4">
              <Rule />
              {[...earned, ...blank].map((seal) => (
                <div
                  key={seal.id}
                  className="flex items-baseline gap-x-4 border-b border-rule py-5"
                >
                  <span
                    className={`shrink-0 self-center ${seal.earnedAt ? 'text-accent' : 'text-rule-strong'}`}
                  >
                    <WaxSeal earned={Boolean(seal.earnedAt)} />
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <h3 className={seal.earnedAt ? 'text-ink' : 'text-muted'}>{seal.name}</h3>
                      <span className="font-mono text-caption tabular-nums text-muted sm:ml-auto">
                        {seal.points} xp
                      </span>
                    </div>
                    <p className="mt-0.5 text-caption text-muted">{seal.requirement}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-20">
            <Reveal>
              <Eyebrow>Courses</Eyebrow>
            </Reveal>
            <Rule className="mt-4" />

            {game.courses.map((standing) => {
              const course = byId.get(standing.courseId)
              if (!course) return null
              return (
                <Reveal key={standing.courseId}>
                  <div className="border-b border-rule py-8">
                    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                      <h2 className="text-section text-ink">{course.name}</h2>
                      <span className="font-mono text-caption tabular-nums text-muted sm:ml-auto">
                        {standing.xp} xp
                      </span>
                    </div>
                    <p className="mt-2 text-caption text-muted">
                      {standing.lessonsCompleted} of {standing.lessonsTotal} lessons ·{' '}
                      {standing.exercisesPassed} of {standing.exercisesTotal} exercises ·{' '}
                      {standing.modulesCompleted} of {standing.modulesTotal} modules
                    </p>
                    <RuleMeter
                      className="mt-3 max-w-sm"
                      fraction={
                        standing.lessonsTotal === 0
                          ? 0
                          : standing.lessonsCompleted / standing.lessonsTotal
                      }
                      label={`${course.name} progress`}
                    />
                  </div>
                </Reveal>
              )
            })}
          </section>
        </Wrap>
      </main>

      <SiteFooter />
    </>
  )
}
