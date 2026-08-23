import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { tokenNeedsRefresh } from './session'

const DAY = 24 * 60 * 60 * 1000
const LIFETIME = 30 * DAY
const NOW = 1_800_000_000_000

describe('tokenNeedsRefresh', () => {
  it('leaves a fresh token alone', () => {
    assert.equal(tokenNeedsRefresh(NOW + 29 * DAY, LIFETIME, NOW), false)
  })

  it('replaces one past halfway', () => {
    assert.equal(tokenNeedsRefresh(NOW + 14 * DAY, LIFETIME, NOW), true)
  })

  it('does not replace exactly at halfway', () => {
    // Strictly past, so a token minted this instant is never immediately stale.
    assert.equal(tokenNeedsRefresh(NOW + 15 * DAY, LIFETIME, NOW), false)
  })

  it('refuses an already expired token', () => {
    // Not stale, finished. Renewing it would make the expiry a formality.
    assert.equal(tokenNeedsRefresh(NOW - 1, LIFETIME, NOW), false)
  })

  it('keeps a daily client alive indefinitely', () => {
    // The property that matters: used every day, it never reaches its expiry.
    let expires = NOW + LIFETIME
    for (let day = 1; day <= 365; day++) {
      const at = NOW + day * DAY
      assert.ok(expires > at, `signed out on day ${day}`)
      if (tokenNeedsRefresh(expires, LIFETIME, at)) expires = at + LIFETIME
    }
  })

  it('still expires a client that stops using it', () => {
    const expires = NOW + LIFETIME
    assert.equal(tokenNeedsRefresh(expires, LIFETIME, NOW + 31 * DAY), false)
  })
})
