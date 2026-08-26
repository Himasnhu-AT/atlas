'use client'

import { useState } from 'react'
import Link from 'next/link'

interface UserRow {
  id: string
  displayName: string
  email: string
  createdAt: string
  totalXp: number
}

export function UserSearchTable({ users }: { users: UserRow[] }) {
  const [query, setQuery] = useState('')

  const filtered = users.filter(
    (u) =>
      u.displayName.toLowerCase().includes(query.toLowerCase()) ||
      u.email.toLowerCase().includes(query.toLowerCase()) ||
      u.id.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, email, or user id…"
          className="w-full max-w-md rounded-field border border-rule bg-paper-raised px-4 py-2 text-caption text-ink placeholder:text-muted focus:border-ink focus:outline-none"
        />
        <span className="text-caption text-muted">{filtered.length} learners</span>
      </div>

      <div className="overflow-x-auto rounded-sheet border border-rule bg-paper">
        <table className="w-full border-collapse text-left text-caption">
          <thead>
            <tr className="border-b border-rule bg-paper-raised text-muted">
              <th className="px-4 py-3 font-medium">Learner</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Total XP</th>
              <th className="px-4 py-3 font-medium">Joined</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted">
                  No learners found.
                </td>
              </tr>
            ) : (
              filtered.map((user) => (
                <tr key={user.id} className="transition-colors hover:bg-paper-raised">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex size-8 items-center justify-center rounded-full border border-rule-strong font-medium text-ink">
                        {user.displayName.slice(0, 1).toUpperCase() || '?'}
                      </span>
                      <span className="font-medium text-ink">{user.displayName}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-[12px] text-ink-soft">
                    {user.email}
                  </td>
                  <td className="px-4 py-3 font-medium text-ink">{user.totalXp} XP</td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(user.createdAt).toLocaleDateString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/admin/users/${user.id}`}
                      className="inline-flex min-h-8 items-center rounded-field border border-rule px-3 text-[12px] font-medium text-ink hover:bg-paper-sunken"
                    >
                      View Profile
                    </Link>
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
