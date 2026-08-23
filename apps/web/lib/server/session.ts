import 'server-only'

import {
  createHmac,
  randomBytes,
  randomUUID,
  scrypt as scryptCallback,
  timingSafeEqual,
} from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { promisify } from 'node:util'
import { cookies } from 'next/headers'

import { tokenNeedsRefresh, type User } from '@atlas/core'

import { store, userId as deriveUserId, type StoredUser } from './store'

const scrypt = promisify(scryptCallback)

const COOKIE = 'atlas_session'
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30

/**
 * Sessions and passwords.
 *
 * The web app carries a signed httpOnly cookie. The desktop app sends the same
 * token as a bearer header. Either way the server derives the user id itself and
 * never reads one from a request body.
 */

let cachedSecret: string | null = null

/**
 * The key sessions are signed with.
 *
 * SESSION_SECRET is the right answer. When it is absent the server generates a
 * random one and writes it to .data/session-secret so restarts do not sign
 * everybody out. That keeps a fresh checkout working with no configuration.
 *
 * The generated file is per machine, so a multi-instance deployment would give
 * each instance a different key and sessions would break as requests moved
 * between them. Set SESSION_SECRET before deploying anywhere real, which is
 * what the warning below says.
 */
function secret(): string {
  if (cachedSecret) return cachedSecret

  const configured = process.env.SESSION_SECRET
  if (configured) {
    cachedSecret = configured
    return configured
  }

  const file = path.join(process.cwd(), '.data', 'session-secret')
  try {
    cachedSecret = readFileSync(file, 'utf8').trim()
    if (cachedSecret) return cachedSecret
  } catch {
    // Not generated yet.
  }

  const generated = randomBytes(32).toString('hex')
  try {
    mkdirSync(path.dirname(file), { recursive: true })
    writeFileSync(file, generated, { mode: 0o600 })
  } catch {
    // Read-only filesystem. Sessions will not survive a restart, which is
    // worth knowing about but not worth refusing to start over.
  }

  console.warn(
    'SESSION_SECRET is not set. Generated one in .data/session-secret. ' +
      'Set SESSION_SECRET explicitly before deploying: a generated key is per ' +
      'machine and will not work across multiple instances.',
  )

  cachedSecret = generated
  return generated
}

export async function hashPassword(
  password: string,
  salt = randomBytes(16).toString('hex'),
): Promise<{ hash: string; salt: string }> {
  const derived = (await scrypt(password, salt, 64)) as Buffer
  return { hash: derived.toString('hex'), salt }
}

export async function verifyPassword(password: string, user: StoredUser): Promise<boolean> {
  const { hash } = await hashPassword(password, user.passwordSalt)
  const a = Buffer.from(hash, 'hex')
  const b = Buffer.from(user.passwordHash, 'hex')
  // Constant time, and length-checked first because timingSafeEqual throws on
  // a length mismatch.
  return a.length === b.length && timingSafeEqual(a, b)
}

function sign(payload: string): string {
  return createHmac('sha256', secret()).update(payload).digest('base64url')
}

/**
 * Mint a session token.
 *
 * `deviceId` scopes the token to a paired device so it can be revoked. Without
 * it a token is a stateless HMAC good for thirty days, and the only way to
 * revoke one is to rotate `SESSION_SECRET`, which signs everybody out. For a
 * token sitting on somebody's laptop for a month that is not an acceptable
 * answer to "I lost it".
 *
 * The payload gains a fourth part. That is backward compatible by construction:
 * the signature split uses `lastIndexOf`, and the parse below reads positions 0
 * and 1, so a three-part cookie minted before this still verifies and still
 * resolves to its user.
 */
export function createToken(userId: string, deviceId?: string): string {
  const expires = Date.now() + MAX_AGE_SECONDS * 1000
  const payload = `${userId}.${expires}.${randomUUID()}${deviceId ? `.${deviceId}` : ''}`
  return `${Buffer.from(payload).toString('base64url')}.${sign(payload)}`
}

export interface TokenClaims {
  userId: string
  /** Present only on a token minted for a paired device. */
  deviceId?: string
  /** Epoch ms this token stops verifying. */
  expiresAt: number
}

export function readToken(token: string | undefined): TokenClaims | null {
  if (!token) return null

  const separator = token.lastIndexOf('.')
  if (separator === -1) return null

  const encoded = token.slice(0, separator)
  const signature = token.slice(separator + 1)

  let payload: string
  try {
    payload = Buffer.from(encoded, 'base64url').toString()
  } catch {
    return null
  }

  const expected = sign(payload)
  const a = Buffer.from(signature)
  const b = Buffer.from(expected)
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null

  const [userId, expires, , deviceId] = payload.split('.')
  if (!userId || !expires) return null
  const expiresAt = Number(expires)
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) return null

  return { userId, deviceId: deviceId || undefined, expiresAt }
}

export async function setSessionCookie(token: string): Promise<void> {
  const jar = await cookies()
  jar.set(COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: MAX_AGE_SECONDS,
  })
}

export async function clearSessionCookie(): Promise<void> {
  const jar = await cookies()
  jar.delete(COOKIE)
}

/**
 * The current user, from a cookie or a bearer token.
 *
 * Every authenticated route goes through here. Nothing derives a user id from
 * request input.
 */
export async function currentUser(request?: Request): Promise<User | null> {
  let token: string | undefined
  let bearer = false

  const header = request?.headers.get('authorization')
  if (header?.startsWith('Bearer ')) {
    token = header.slice(7)
    bearer = true
  } else {
    token = (await cookies()).get(COOKIE)?.value
  }

  const claims = readToken(token)
  if (!claims) return null

  // The revocation lookup is on the bearer path only. A cookie is a browser
  // session the person can end by signing out, and making every page render pay
  // for a device lookup would be a cost with no matching risk.
  if (bearer && claims.deviceId) {
    const device = await store().findDevice(claims.deviceId)
    if (!device || device.userId !== claims.userId || device.revokedAt) return null
    await store().touchDevice(claims.deviceId)
  }

  const record = await store().findUserById(claims.userId)
  if (!record) return null

  const { passwordHash, passwordSalt, ...user } = record
  void passwordHash
  void passwordSalt
  return user
}

/** The device a request came from, if it came from one. */
export async function currentDeviceId(request?: Request): Promise<string | undefined> {
  const header = request?.headers.get('authorization')
  if (!header?.startsWith('Bearer ')) return undefined
  return readToken(header.slice(7))?.deviceId
}

export async function requireUser(request?: Request): Promise<User> {
  const user = await currentUser(request)
  if (!user) throw new UnauthorizedError()
  return user
}

export class UnauthorizedError extends Error {
  constructor() {
    super('not signed in')
    this.name = 'UnauthorizedError'
  }
}

export { deriveUserId }

/**
 * A replacement token for this request, or null if it does not need one.
 *
 * Stateless on purpose. The obvious implementation is for `currentUser` to
 * stash what it minted in a module variable and have `route` pick it up, and
 * that is a cross-request token leak: route handlers run concurrently in one
 * process, so two requests interleaving between the stash and the read hand one
 * user the other user's token. Reading the request again costs an HMAC verify
 * and cannot do that.
 *
 * Only ever called after a handler has succeeded, so a token belonging to a
 * deleted or revoked account has already been turned away with a 401.
 */
export function refreshedTokenFor(request: Request): { token: string; bearer: boolean } | null {
  const header = request.headers.get('authorization')
  if (!header?.startsWith('Bearer ')) return null

  const claims = readToken(header.slice(7))
  if (!claims || !tokenNeedsRefresh(claims.expiresAt, MAX_AGE_SECONDS * 1000, Date.now()))
    return null

  return { token: createToken(claims.userId, claims.deviceId), bearer: true }
}
