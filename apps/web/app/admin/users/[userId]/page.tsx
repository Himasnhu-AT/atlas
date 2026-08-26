import Link from 'next/link'
import { notFound } from 'next/navigation'

import { store } from '@/lib/server/store'
import { ModerationControls } from './moderation-controls'

export default async function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ userId: string }>
}) {
  const { userId } = await params
  const user = await store().findUserById(userId)
  if (!user) notFound()

  const [progress, game, awards, seals, stats, devices] = await Promise.all([
    store().progressFor(userId),
    store().gameFor(userId),
    store().awardsFor(userId),
    store().sealsFor(userId),
    store().exerciseStats(userId),
    store().devicesFor(userId),
  ])

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/admin/users"
          className="text-caption text-muted hover:text-ink"
        >
          ← Back to Learners
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-4">
          <h1 className="font-serif text-display text-ink">{user.displayName}</h1>
          <span className="font-mono text-caption text-muted">ID: {user.id}</span>
        </div>
        <p className="font-mono text-caption text-ink-soft">{user.email}</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-sheet border border-rule bg-paper-raised p-4">
          <p className="text-caption text-muted">Total XP</p>
          <p className="mt-1 font-serif text-[28px] font-semibold text-ink">
            {game.totalXp}
          </p>
        </div>
        <div className="rounded-sheet border border-rule bg-paper-raised p-4">
          <p className="text-caption text-muted">Weekly Target</p>
          <p className="mt-1 font-serif text-[28px] font-semibold text-ink">
            {game.weeklyTarget} days
          </p>
          <p className="text-[12px] text-muted">
            {game.weeklyTargetChosen ? 'Chosen by student' : 'Default value'}
          </p>
        </div>
        <div className="rounded-sheet border border-rule bg-paper-raised p-4">
          <p className="text-caption text-muted">Best Streak</p>
          <p className="mt-1 font-serif text-[28px] font-semibold text-ink">
            {game.bestWeeks} weeks
          </p>
        </div>
        <div className="rounded-sheet border border-rule bg-paper-raised p-4">
          <p className="text-caption text-muted">Leaderboard</p>
          <p className="mt-1 font-serif text-[28px] font-semibold text-ink">
            {game.leaderboardExcluded
              ? 'Excluded'
              : game.leaderboardOptIn
                ? 'Active'
                : 'Not Joined'}
          </p>
        </div>
      </div>

      {/* Moderation Controls */}
      <ModerationControls userId={userId} initialExcluded={game.leaderboardExcluded} />

      {/* Modules & Lessons Progress */}
      <div className="rounded-sheet border border-rule bg-paper-raised p-6">
        <h2 className="font-serif text-title text-ink">Curriculum Progress</h2>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-caption font-medium text-muted">Modules ({progress.modules.length})</h3>
            <div className="mt-2 divide-y divide-rule rounded-field border border-rule bg-paper">
              {progress.modules.length === 0 ? (
                <p className="p-3 text-caption text-muted">No module progress yet.</p>
              ) : (
                progress.modules.map((m) => (
                  <div key={m.moduleId} className="flex items-center justify-between p-3 text-caption">
                    <span className="font-medium text-ink">{m.moduleId}</span>
                    <span className="capitalize text-muted">
                      {m.status} ({m.lessonsCompleted}/{m.lessonsTotal} lessons)
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <h3 className="text-caption font-medium text-muted">Lessons Completed ({progress.lessons.filter((l) => l.status === 'completed').length})</h3>
            <div className="mt-2 max-h-60 overflow-y-auto divide-y divide-rule rounded-field border border-rule bg-paper">
              {progress.lessons.length === 0 ? (
                <p className="p-3 text-caption text-muted">No lessons recorded yet.</p>
              ) : (
                progress.lessons.map((l) => (
                  <div key={l.lessonId} className="flex items-center justify-between p-3 text-caption">
                    <span className="font-mono text-[12px] text-ink">{l.lessonId}</span>
                    <span className="capitalize text-muted">{l.status} · {l.secondsSpent}s</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Exercise Performance */}
      <div className="rounded-sheet border border-rule bg-paper-raised p-6">
        <h2 className="font-serif text-title text-ink">Exercise Performance ({stats.length})</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-caption">
            <thead>
              <tr className="border-b border-rule text-muted">
                <th className="py-2">Exercise ID</th>
                <th className="py-2">Passes</th>
                <th className="py-2">Failures Before Pass</th>
                <th className="py-2">Total Failures</th>
                <th className="py-2">Best Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {stats.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-muted">
                    No exercise attempts.
                  </td>
                </tr>
              ) : (
                stats.map((s) => (
                  <tr key={s.exerciseId}>
                    <td className="py-2 font-mono text-[12px] text-ink">{s.exerciseId}</td>
                    <td className="py-2 text-ink">{s.passes}</td>
                    <td className="py-2 text-ink">{s.failuresBeforePass}</td>
                    <td className="py-2 text-ink">{s.failures}</td>
                    <td className="py-2 text-muted">
                      {s.bestPassDurationMs ? `${s.bestPassDurationMs}ms` : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* XP Awards Ledger & Seals */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="rounded-sheet border border-rule bg-paper-raised p-6">
          <h2 className="font-serif text-title text-ink">Earned Seals ({seals.length})</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {seals.length === 0 ? (
              <p className="text-caption text-muted">No seals earned yet.</p>
            ) : (
              seals.map((seal) => (
                <span
                  key={seal.sealId}
                  className="rounded-field border border-rule bg-paper px-3 py-1 text-caption font-medium text-ink"
                >
                  🏆 {seal.sealId}
                </span>
              ))
            )}
          </div>
        </div>

        <div className="rounded-sheet border border-rule bg-paper-raised p-6">
          <h2 className="font-serif text-title text-ink">Paired Devices ({devices.length})</h2>
          <div className="mt-4 divide-y divide-rule">
            {devices.length === 0 ? (
              <p className="text-caption text-muted">No devices registered.</p>
            ) : (
              devices.map((d) => (
                <div key={d.id} className="flex items-center justify-between py-2 text-caption">
                  <div>
                    <p className="font-medium text-ink">{d.name} ({d.platform})</p>
                    <p className="text-[11px] text-muted">v{d.appVersion} · Last seen {new Date(d.lastSeenAt).toLocaleDateString()}</p>
                  </div>
                  {d.revokedAt && <span className="text-[11px] text-rose-500 font-medium">Revoked</span>}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Awards Ledger */}
      <div className="rounded-sheet border border-rule bg-paper-raised p-6">
        <h2 className="font-serif text-title text-ink">XP Ledger ({awards.length} awards)</h2>
        <div className="mt-4 max-h-80 overflow-y-auto">
          <table className="w-full text-left text-caption">
            <thead>
              <tr className="border-b border-rule text-muted">
                <th className="py-2">Award Key</th>
                <th className="py-2">Kind</th>
                <th className="py-2">Points</th>
                <th className="py-2">Awarded At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {awards.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-muted">
                    No awards on ledger.
                  </td>
                </tr>
              ) : (
                awards.map((a) => (
                  <tr key={a.awardKey}>
                    <td className="py-2 font-mono text-[11px] text-ink">{a.awardKey}</td>
                    <td className="py-2 capitalize text-muted">{a.kind}</td>
                    <td className="py-2 font-medium text-emerald-600">+{a.points} XP</td>
                    <td className="py-2 text-[12px] text-muted">
                      {new Date(a.awardedAt).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
