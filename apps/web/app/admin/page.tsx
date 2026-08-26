import Link from 'next/link'

import { store } from '@/lib/server/store'

export default async function AdminDashboardPage() {
  const stats = await store().adminStats()
  const recentUsers = (await store().listAllUsers()).slice(0, 5)
  const recentAttempts = await store().listRecentAttempts(6)

  const passRate =
    stats.totalAttempts > 0
      ? Math.round((stats.totalPassed / stats.totalAttempts) * 100)
      : 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-serif text-display text-ink">Platform Overview</h1>
        <p className="mt-1 font-serif text-lead text-ink-soft">
          System telemetry, learner engagement, and platform health.
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-sheet border border-rule bg-paper-raised p-5">
          <p className="text-caption text-muted">Total Learners</p>
          <p className="mt-2 font-serif text-[32px] font-semibold text-ink">
            {stats.totalUsers}
          </p>
          <p className="mt-1 text-[12px] text-muted">Registered accounts</p>
        </div>

        <div className="rounded-sheet border border-rule bg-paper-raised p-5">
          <p className="text-caption text-muted">Active Today</p>
          <p className="mt-2 font-serif text-[32px] font-semibold text-ink">
            {stats.activeToday}
          </p>
          <p className="mt-1 text-[12px] text-muted">Touched lesson or exercise</p>
        </div>

        <div className="rounded-sheet border border-rule bg-paper-raised p-5">
          <p className="text-caption text-muted">Total Attempts</p>
          <p className="mt-2 font-serif text-[32px] font-semibold text-ink">
            {stats.totalAttempts}
          </p>
          <p className="mt-1 text-[12px] text-muted">{passRate}% pass rate ({stats.totalPassed} passed)</p>
        </div>

        <div className="rounded-sheet border border-rule bg-paper-raised p-5">
          <p className="text-caption text-muted">Total XP Awarded</p>
          <p className="mt-2 font-serif text-[32px] font-semibold text-ink">
            {stats.totalXp.toLocaleString()}
          </p>
          <p className="mt-1 text-[12px] text-muted">Earned via lessons & quests</p>
        </div>
      </div>

      {/* Two column layout for recent users & recent attempts */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Recent Learners */}
        <div className="rounded-sheet border border-rule bg-paper-raised p-6">
          <div className="flex items-center justify-between border-b border-rule pb-4">
            <h2 className="font-serif text-title text-ink">Recent Learners</h2>
            <Link
              href="/admin/users"
              className="text-caption text-accent hover:underline"
            >
              View all ({stats.totalUsers}) →
            </Link>
          </div>

          <div className="mt-4 divide-y divide-rule">
            {recentUsers.length === 0 ? (
              <p className="py-4 text-caption text-muted">No learners registered yet.</p>
            ) : (
              recentUsers.map((u) => (
                <div key={u.id} className="flex items-center justify-between py-3">
                  <div>
                    <Link
                      href={`/admin/users/${u.id}`}
                      className="font-medium text-ink hover:underline"
                    >
                      {u.displayName}
                    </Link>
                    <p className="font-mono text-[12px] text-muted">{u.email}</p>
                  </div>
                  <span className="text-[12px] text-muted">
                    {new Date(u.createdAt).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Attempts */}
        <div className="rounded-sheet border border-rule bg-paper-raised p-6">
          <div className="flex items-center justify-between border-b border-rule pb-4">
            <h2 className="font-serif text-title text-ink">Recent Exercise Attempts</h2>
            <Link
              href="/admin/attempts"
              className="text-caption text-accent hover:underline"
            >
              View live stream →
            </Link>
          </div>

          <div className="mt-4 divide-y divide-rule">
            {recentAttempts.length === 0 ? (
              <p className="py-4 text-caption text-muted">No exercise attempts logged yet.</p>
            ) : (
              recentAttempts.map((a) => (
                <div key={a.id} className="flex items-center justify-between py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block size-2 rounded-full ${
                          a.passed ? 'bg-emerald-500' : 'bg-rose-500'
                        }`}
                      />
                      <span className="font-mono text-caption font-medium text-ink">
                        {a.exerciseId}
                      </span>
                    </div>
                    <p className="text-[12px] text-muted">
                      Tests: {a.testsPassed}/{a.testsTotal} · {a.durationMs}ms
                    </p>
                  </div>
                  <span className="text-[12px] text-muted">
                    {new Date(a.createdAt).toLocaleTimeString(undefined, {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Backend Engine Card */}
      <div className="rounded-sheet border border-rule bg-paper-raised p-6">
        <h2 className="font-serif text-title text-ink">Storage Infrastructure</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-caption">
          <div>
            <span className="text-muted">Storage Engine</span>
            <p className="font-medium text-ink">Cloud Firestore</p>
          </div>
          <div>
            <span className="text-muted">Firebase Project</span>
            <p className="font-mono text-ink">
              {process.env.FIREBASE_PROJECT_ID || 'synthai-learn'}
            </p>
          </div>
          <div>
            <span className="text-muted">Status</span>
            <p className="font-medium text-emerald-600">Active & Operational</p>
          </div>
        </div>
      </div>
    </div>
  )
}
