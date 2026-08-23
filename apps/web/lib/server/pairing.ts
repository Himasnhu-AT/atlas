import 'server-only'

import { createHash, randomBytes, randomUUID } from 'node:crypto'

import { store, type StoredPairing } from './store'

/**
 * Pairing a desktop device, as a device authorization grant.
 *
 * The flow is the one `gh auth login` uses: the app asks for a code, opens the
 * system browser, an already-signed-in session approves it, and the app polls
 * until it can collect a token.
 *
 * The inverse flow, where the browser shows a code the person types into the
 * app, is the obvious one and is worse. It renders the secret on a web page,
 * where it can be shoulder-surfed or phished onto a page that looks like this
 * one. Here the user code is worthless on its own: approving it requires a
 * logged-in browser, and the actual credential is delivered over a channel keyed
 * by a secret the desktop generated and never showed anyone.
 */

const PAIRING_TTL_MS = 10 * 60 * 1000

/** How often the desktop should poll, in seconds. */
export const POLL_INTERVAL_SECONDS = 3

/**
 * Characters a person can read off one screen and type into another.
 *
 * No 0/O, 1/I/L, 5/S, 2/Z, 8/B. Someone reading a code aloud from a laptop
 * should not have to say "zero, the number".
 */
const ALPHABET = '34679ACDEFGHJKMNPQRTUVWXY'

function userCode(): string {
  const bytes = randomBytes(8)
  const chars = [...bytes].map((b) => ALPHABET[b % ALPHABET.length])
  return `${chars.slice(0, 4).join('')}-${chars.slice(4).join('')}`
}

export function hashDeviceCode(code: string): string {
  return createHash('sha256').update(code).digest('hex')
}

export interface StartedPairing {
  deviceCode: string
  userCode: string
  expiresAt: string
  intervalSeconds: number
}

export async function startPairing(input: {
  name: string
  platform: string
  appVersion: string
}): Promise<StartedPairing> {
  // High entropy, and never stored: the row keeps only its hash.
  const deviceCode = randomBytes(32).toString('base64url')
  const expiresAt = new Date(Date.now() + PAIRING_TTL_MS).toISOString()

  const pairing: StoredPairing = {
    deviceCodeHash: hashDeviceCode(deviceCode),
    userCode: userCode(),
    name: input.name.slice(0, 80),
    platform: input.platform.slice(0, 40),
    appVersion: input.appVersion.slice(0, 40),
    createdAt: new Date().toISOString(),
    expiresAt,
  }

  await store().createPairing(pairing)

  return {
    deviceCode,
    userCode: pairing.userCode,
    expiresAt,
    intervalSeconds: POLL_INTERVAL_SECONDS,
  }
}

export type PollResult =
  | { status: 'pending' }
  | { status: 'expired' }
  | { status: 'approved'; deviceId: string; userId: string }

/**
 * Collect the result of a pairing, once.
 *
 * On approval the pairing row is deleted and a device row takes its place, so a
 * device code is good for exactly one token. Replaying it afterwards reports
 * `expired`, which is true: there is nothing left to collect.
 */
export async function collectPairing(deviceCode: string): Promise<PollResult> {
  const hash = hashDeviceCode(deviceCode)
  const pairing = await store().findPairingByCodeHash(hash)
  if (!pairing) return { status: 'expired' }
  if (!pairing.approvedAt || !pairing.userId) return { status: 'pending' }

  const deviceId = randomUUID()
  const now = new Date().toISOString()

  await store().createDevice({
    id: deviceId,
    userId: pairing.userId,
    name: pairing.name,
    platform: pairing.platform,
    appVersion: pairing.appVersion,
    createdAt: now,
    lastSeenAt: now,
  })
  await store().deletePairing(hash)

  return { status: 'approved', deviceId, userId: pairing.userId }
}
