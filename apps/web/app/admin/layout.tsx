import Link from 'next/link'
import type { ReactNode } from 'react'

import { requireAdmin } from '@/lib/server/admin'

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const user = await requireAdmin()

  return (
    <div className="min-h-screen bg-paper">
      <div className="border-b border-rule bg-paper-raised">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-6 sm:px-8">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="font-serif text-title font-medium text-ink">SynthAI Labs</span>
              <span className="rounded bg-ink px-1.5 py-0.5 text-[11px] font-mono uppercase tracking-wider text-paper">
                Admin
              </span>
            </div>

            <nav className="flex items-center gap-5 text-caption font-medium text-ink-soft">
              <Link href="/admin" className="hover:text-ink">
                Overview
              </Link>
              <Link href="/admin/users" className="hover:text-ink">
                Learners
              </Link>
              <Link href="/admin/attempts" className="hover:text-ink">
                Attempts
              </Link>
              <Link href="/admin/devices" className="hover:text-ink">
                Devices
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-4 text-caption">
            <span className="hidden font-mono text-[12px] text-muted sm:inline">
              Engine: <span className="text-ink">Firebase Firestore</span>
            </span>
            <span className="text-muted">|</span>
            <span className="text-muted">{user.email}</span>
            <Link
              href="/"
              className="rounded-field border border-rule px-2.5 py-1 text-[12px] text-ink hover:bg-paper-sunken"
            >
              Exit to Site
            </Link>
          </div>
        </div>
      </div>

      <main className="mx-auto w-full max-w-page px-6 py-8 sm:px-8">{children}</main>
    </div>
  )
}
