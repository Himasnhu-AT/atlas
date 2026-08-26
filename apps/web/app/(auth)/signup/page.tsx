import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { AuthForm } from '@/components/auth-form'
import { currentUser } from '@/lib/server/session'
import { safeNext } from '@/lib/safe-next'

export const metadata: Metadata = { title: 'Create an account' }

export default async function SignupPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>
}) {
  const { next } = await searchParams
  const destination = safeNext(next)

  if (await currentUser()) redirect(destination)

  return <AuthForm mode="signup" next={destination} />
}
