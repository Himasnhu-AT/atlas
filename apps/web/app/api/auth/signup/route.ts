import { SignupRequest } from '@learn/core'

import { fail, json, parseBody, route } from '@/lib/server/respond'
import { createToken, hashPassword, setSessionCookie } from '@/lib/server/session'
import { store, userId } from '@/lib/server/store'

export const POST = route(async (request) => {
  const body = await parseBody(request, SignupRequest)
  const email = body.email.trim().toLowerCase()

  if (await store().findUserByEmail(email)) {
    return fail(409, 'email_taken', 'an account with that email already exists')
  }

  const { hash, salt } = await hashPassword(body.password)
  const id = userId(email)

  await store().createUser({
    id,
    email,
    displayName: body.displayName.trim(),
    createdAt: new Date().toISOString(),
    passwordHash: hash,
    passwordSalt: salt,
  })

  await setSessionCookie(createToken(id))

  const user = await store().findUserById(id)
  return json(
    {
      id,
      email,
      displayName: user?.displayName ?? body.displayName,
      createdAt: user?.createdAt ?? new Date().toISOString(),
    },
    201,
  )
})
