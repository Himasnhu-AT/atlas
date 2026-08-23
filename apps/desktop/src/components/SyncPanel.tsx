import { useCallback, useState } from 'react'
import { cn } from '@atlas/ui'

import { usePairing, useSync } from '../lib/sync'

/**
 * Account and sync, in the header.
 *
 * Signed out, this says what is waiting rather than nagging. Practice works with
 * no account and always has; the offer is that a backlog can be credited later,
 * not that syncing is required to continue.
 */
export function SyncPanel() {
  const sync = useSync()
  const [open, setOpen] = useState(false)

  const onPaired = useCallback(
    (account: Parameters<typeof sync.setAccount>[0]) => {
      sync.setAccount(account)
      setOpen(false)
      void sync.drain()
    },
    [sync],
  )

  const pairing = usePairing(onPaired)

  const label = sync.signedOut
    ? 'Disconnected'
    : sync.account
      ? sync.pending > 0
        ? `${sync.pending} to sync`
        : 'Synced'
      : sync.pending > 0
        ? `${sync.pending} saved`
        : 'Not connected'

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className={cn(
          'inline-flex h-8 items-center gap-2 rounded-field px-2.5 text-xs',
          'transition-colors duration-150 hover:bg-paper-sunken',
          sync.signedOut ? 'text-fail' : 'text-muted hover:text-ink',
        )}
      >
        <span
          aria-hidden
          className={cn(
            'size-1.5 rounded-full',
            sync.signedOut
              ? 'bg-fail'
              : sync.account
                ? sync.pending > 0
                  ? 'bg-warn'
                  : 'bg-pass'
                : 'bg-rule-strong',
          )}
        />
        {label}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-sheet border border-rule bg-paper-raised p-4 text-xs">
          {sync.signedOut && (
            <p className="mb-3 text-fail">
              This device was disconnected from the account. Your work is still saved here and
              will sync once you connect again.
            </p>
          )}

          {sync.account && !sync.signedOut ? (
            <>
              <p className="font-medium text-ink">{sync.account.displayName}</p>
              <p className="mt-0.5 text-muted">{sync.account.email}</p>
              <p className="mt-3 text-muted">
                {sync.pending > 0
                  ? `${sync.pending} result${sync.pending === 1 ? '' : 's'} waiting to sync.`
                  : 'Everything here is synced.'}
              </p>
              {sync.lastResult?.detail && (
                <p className="mt-2 text-warn">{sync.lastResult.detail}</p>
              )}
              <button
                type="button"
                onClick={() => void sync.drain()}
                disabled={sync.busy}
                className="mt-3 inline-flex h-8 items-center rounded-field border border-rule px-3 text-xs text-ink-soft hover:border-rule-strong hover:text-ink disabled:opacity-60"
              >
                {sync.busy ? 'Syncing…' : 'Sync now'}
              </button>
            </>
          ) : pairing.session ? (
            <>
              <p className="text-ink">Enter this code in your browser.</p>
              <p className="mt-3 font-mono text-lg tracking-[0.18em] text-ink">
                {pairing.session.userCode}
              </p>
              <p className="mt-3 break-all text-muted">
                {pairing.session.verificationUriComplete}
              </p>
              {pairing.session.expired ? (
                <p className="mt-3 text-warn">That code expired. Start again.</p>
              ) : (
                <p className="mt-3 text-muted">Waiting for you to approve it…</p>
              )}
              <button
                type="button"
                onClick={pairing.cancel}
                className="mt-3 inline-flex h-8 items-center px-2 text-xs text-muted hover:text-ink"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <p className="text-ink">Practice works without an account.</p>
              <p className="mt-2 text-muted">
                {sync.pending > 0
                  ? `${sync.pending} result${sync.pending === 1 ? '' : 's'} are saved on this machine. Connect an account and they all count.`
                  : 'Connect an account to keep your progress across machines.'}
              </p>
              {pairing.error && <p className="mt-2 text-fail">{pairing.error}</p>}
              <button
                type="button"
                onClick={() => void pairing.start(deviceName(), platformName())}
                disabled={pairing.starting}
                className="mt-3 inline-flex h-8 items-center rounded-field bg-ink px-3 text-xs font-medium text-paper hover:bg-accent-deep disabled:opacity-60"
              >
                {pairing.starting ? 'Starting…' : 'Connect an account'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * A name a person will recognise in a list of connected devices.
 *
 * The browser will not tell us the machine's name, so this is the honest
 * approximation: what it is, not who owns it.
 */
function deviceName(): string {
  const platform = platformName()
  return platform === 'macos'
    ? 'Mac'
    : platform === 'windows'
      ? 'Windows PC'
      : platform === 'linux'
        ? 'Linux machine'
        : 'Practice app'
}

function platformName(): string {
  const agent = navigator.userAgent
  if (/Mac/i.test(agent)) return 'macos'
  if (/Win/i.test(agent)) return 'windows'
  if (/Linux|X11/i.test(agent)) return 'linux'
  return 'unknown'
}
