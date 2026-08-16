import { Credentials } from '@learn/core'

import { fail, json, parseBody, route } from '@/lib/server/respond'
import { createToken, setSessionCookie, verifyPassword } from '@/lib/server/session'
import { store } from '@/lib/server/store'

export const POST = route(async (request) => {
  const body = await parseBody(request, Credentials)
  const user = await store().findUserByEmail(body.email.trim().toLowerCase())

  // One message for both "no such user" and "wrong password", so the endpoint
  // cannot be used to find out which addresses have accounts.
  const invalid = () => fail(401, 'invalid_credentials', 'that email or password is wrong')

  if (!user) {
    // Still do the work, so a missing account is not detectably faster.
    await verifyPassword(body.password, {
      ...(await placeholderUser()),
    })
    return invalid()
  }

  if (!(await verifyPassword(body.password, user))) return invalid()

  await setSessionCookie(createToken(user.id))
  await store().touchUser(user.id)

  const { passwordHash, passwordSalt, ...safe } = user
  void passwordHash
  void passwordSalt
  return json(safe)
})

/** A throwaway record so the no-such-user path costs the same scrypt work. */
async function placeholderUser() {
  const { hashPassword } = await import('@/lib/server/session')
  const { hash, salt } = await hashPassword('placeholder')
  return {
    id: '',
    email: '',
    displayName: '',
    createdAt: new Date().toISOString(),
    passwordHash: hash,
    passwordSalt: salt,
  }
}
