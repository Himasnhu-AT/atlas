import 'server-only'

import { redirect } from 'next/navigation'
import type { User } from '@atlas/core'
import { currentUser } from './session'

const DEFAULT_ADMINS = ['you@example.com']

export function getAdminEmails(): string[] {
  const envAdmins = (process.env.ADMIN_EMAILS ?? '')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
  return Array.from(new Set([...DEFAULT_ADMINS, ...envAdmins]))
}

export function isAdmin(email?: string | null): boolean {
  if (!email) return false
  const list = getAdminEmails()
  return list.includes(email.trim().toLowerCase())
}

export class ForbiddenError extends Error {
  constructor(message = 'forbidden: admin privileges required') {
    super(message)
    this.name = 'ForbiddenError'
  }
}

export async function requireAdmin(request?: Request): Promise<User> {
  const user = await currentUser(request)
  if (!user) {
    redirect('/login?next=/admin')
  }
  if (!isAdmin(user.email)) {
    redirect('/')
  }
  return user
}
