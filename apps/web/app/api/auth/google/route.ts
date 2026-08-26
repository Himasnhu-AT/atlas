import { z } from 'zod'
import { getAuth } from 'firebase-admin/auth'

import { fail, json, parseBody, route } from '@/lib/server/respond'
import { createToken, setSessionCookie, deriveUserId } from '@/lib/server/session'
import { store, type StoredUser } from '@/lib/server/store'

const GoogleAuthPayload = z.object({
  idToken: z.string().min(1),
  displayName: z.string().optional(),
})

export const POST = route(async (request) => {
  const body = await parseBody(request, GoogleAuthPayload)

  let email: string | undefined
  let name: string | undefined

  try {
    const decoded = await getAuth().verifyIdToken(body.idToken)
    email = decoded.email?.trim().toLowerCase()
    name = decoded.name || body.displayName || email?.split('@')[0] || 'Learner'
  } catch (err) {
    console.error('Google ID token verification failed:', err)
    return fail(401, 'invalid_token', 'Google authentication token is invalid or expired')
  }

  if (!email) {
    return fail(400, 'missing_email', 'Google account does not provide an email address')
  }

  const userEmail = email
  const userDisplayName = name || userEmail.split('@')[0] || 'Learner'

  let user = await store().findUserByEmail(userEmail)

  if (!user) {
    const id = deriveUserId(userEmail)
    const newUser: StoredUser = {
      id,
      email: userEmail,
      displayName: userDisplayName,
      createdAt: new Date().toISOString(),
      passwordHash: '',
      passwordSalt: '',
    }
    await store().createUser(newUser)
    user = newUser
  }

  await setSessionCookie(createToken(user.id))
  await store().touchUser(user.id)

  const { passwordHash, passwordSalt, ...safe } = user
  void passwordHash
  void passwordSalt
  return json(safe)
})
