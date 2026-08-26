import Link from 'next/link'

import { store } from '@/lib/server/store'

export default async function AdminAttemptsPage() {
  const attempts = await store().listRecentAttempts(100)
  const users = await store().listAllUsers()
  const usersMap = new Map(users.map((u) => [u.id, u.displayName]))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-display text-ink">Exercise Attempts Stream</h1>
        <p className="mt-1 font-serif text-lead text-ink-soft">
          Recent live exercise runs, test passes, failures, and execution output.
        </p>
      </div>

      <div className="overflow-x-auto rounded-sheet border border-rule bg-paper">
        <table className="w-full border-collapse text-left text-caption">
          <thead>
            <tr className="border-b border-rule bg-paper-raised text-muted">
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Exercise</th>
              <th className="px-4 py-3 font-medium">Learner</th>
              <th className="px-4 py-3 font-medium">Tests</th>
              <th className="px-4 py-3 font-medium">Duration</th>
              <th className="px-4 py-3 font-medium">Timestamp</th>
              <th className="px-4 py-3 font-medium">Output Tail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {attempts.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted">
                  No exercise attempts logged yet.
                </td>
              </tr>
            ) : (
              attempts.map((attempt) => (
                <tr key={attempt.id} className="hover:bg-paper-raised">
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-field px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider ${
                        attempt.passed
                          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                          : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                      }`}
                    >
                      {attempt.passed ? 'Passed' : 'Failed'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] font-medium text-ink">
                    {attempt.exerciseId}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/users/${attempt.userId}`}
                      className="font-medium text-ink hover:underline"
                    >
                      {usersMap.get(attempt.userId) || attempt.userId.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ink-soft">
                    {attempt.testsPassed} / {attempt.testsTotal}
                  </td>
                  <td className="px-4 py-3 text-muted">{attempt.durationMs}ms</td>
                  <td className="px-4 py-3 text-[12px] text-muted">
                    {new Date(attempt.createdAt).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3 font-mono text-[11px] text-muted">
                    {attempt.stdoutTail ? (
                      <span title={attempt.stdoutTail}>{attempt.stdoutTail.slice(0, 60)}…</span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
