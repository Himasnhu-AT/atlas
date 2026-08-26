import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { AuthForm } from '@/components/auth-form'
import { currentUser } from '@/lib/server/session'
import { safeNext } from '@/lib/safe-next'

export const metadata: Metadata = { title: 'Sign in' }

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>
}) {
  const { next } = await searchParams
  const destination = safeNext(next)

  if (await currentUser()) redirect(destination)

  return <AuthForm mode="login" next={destination} />
}
