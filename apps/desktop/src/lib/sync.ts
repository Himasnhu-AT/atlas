import { useCallback, useEffect, useRef, useState } from 'react'

import {
  authAccount,
  authClear,
  syncDrain,
  syncPairPoll,
  syncPairStart,
  syncPending,
  type Account,
  type DrainResult,
  DesktopUnavailableError,
  type PairStart,
} from './ipc'

/**
 * Syncing, from the frontend's point of view.
 *
 * Everything that touches the network or the token happens in Rust. This hook
 * asks for a drain and is told what happened; it never holds a credential and
 * never makes a request itself.
 */

/** Quiet enough not to matter, often enough that a finished session lands. */
const POLL_MS = 30_000

export interface SyncState {
  account: Account | null
  pending: number
  busy: boolean
  /** Set when the server rejected this device. Loud on purpose. */
  signedOut: boolean
  lastResult: DrainResult | null
}

export function useSync() {
  const [state, setState] = useState<SyncState>({
    account: null,
    pending: 0,
    busy: false,
    signedOut: false,
    lastResult: null,
  })
  const draining = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const [account, pending] = await Promise.all([authAccount(), syncPending()])
      setState((previous) => ({ ...previous, account, pending: pending.count }))
    } catch (error) {
      // In the browser build there is no IPC at all, which is expected rather
      // than broken.
      if (!(error instanceof DesktopUnavailableError)) {
        console.warn('[desktop] could not read sync state', error)
      }
    }
  }, [])

  const drain = useCallback(async () => {
    if (draining.current) return
    draining.current = true
    setState((previous) => ({ ...previous, busy: true }))

    try {
      const result = await syncDrain()
      setState((previous) => ({
        ...previous,
        busy: false,
        pending: result.remaining,
        lastResult: result,
        // A revoked device has to say so. A silent 401 that quietly stops the
        // outbox is how somebody's progress freezes for a month unnoticed.
        signedOut: result.status === 'unauthorized',
      }))
      if (result.status === 'unauthorized') await authClear().catch(() => undefined)
      await refresh()
    } catch (error) {
      if (!(error instanceof DesktopUnavailableError)) {
        console.warn('[desktop] sync failed', error)
      }
      setState((previous) => ({ ...previous, busy: false }))
    } finally {
      draining.current = false
    }
  }, [refresh])

  useEffect(() => {
    void refresh()
    void drain()

    // Focus rather than a tight timer: coming back to the window is when a
    // learner is most likely to look at the number, and a laptop that has been
    // shut all night should not have been polling into a dead network.
    const onFocus = () => void drain()
    window.addEventListener('focus', onFocus)
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') void drain()
    }, POLL_MS)

    return () => {
      window.removeEventListener('focus', onFocus)
      clearInterval(timer)
    }
  }, [drain, refresh])

  return { ...state, drain, refresh, setAccount: (account: Account | null) =>
    setState((previous) => ({ ...previous, account, signedOut: false })) }
}

export interface PairingSession extends PairStart {
  /** Stops when the code expires, so a forgotten dialog does not poll forever. */
  expired: boolean
}

/**
 * The pairing handshake.
 *
 * Start, open the browser, poll. The token is stored by Rust when it arrives and
 * is never returned here.
 */
export function usePairing(onPaired: (account: Account) => void) {
  const [session, setSession] = useState<PairingSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)

  const start = useCallback(async (name: string, platform: string) => {
    setStarting(true)
    setError(null)
    try {
      const started = await syncPairStart(name, platform)
      setSession({ ...started, expired: false })

      const { open } = await import('@tauri-apps/plugin-shell')
      await open(started.verificationUriComplete).catch(() => {
        // The capability scope refused it, or there is no browser. The code and
        // the URL are on screen either way, so this is a degradation rather
        // than a failure.
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setStarting(false)
    }
  }, [])

  const cancel = useCallback(() => {
    setSession(null)
    setError(null)
  }, [])

  useEffect(() => {
    if (!session || session.expired) return

    let cancelled = false
    const timer = setInterval(async () => {
      try {
        const poll = await syncPairPoll(session.deviceCode)
        if (cancelled) return

        if (poll.status === 'approved' && poll.account) {
          setSession(null)
          onPaired(poll.account)
        } else if (poll.status === 'expired') {
          setSession((previous) => (previous ? { ...previous, expired: true } : null))
        }
      } catch {
        // A dropped connection mid-pairing is not worth ending the attempt over.
      }
    }, Math.max(1, session.intervalSeconds) * 1000)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [session, onPaired])

  return { session, error, starting, start, cancel }
}
