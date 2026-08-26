'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'

import { signInWithGoogle } from '@/lib/client/firebase'

interface Props {
  mode: 'login' | 'signup'
  next: string
}

/**
 * Sign in and sign up share every mechanic except one field and one endpoint,
 * so they share a component rather than drifting apart over time.
 */
export function AuthForm({ mode, next }: Props) {
  const isSignup = mode === 'signup'
  const router = useRouter()

  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [googleBusy, setGoogleBusy] = useState(false)

  function validate(): string | null {
    if (isSignup && displayName.trim().length === 0) return 'Enter the name you go by.'
    if (!email.includes('@')) return 'That email address is missing an @.'
    if (password.length < 8) return 'Passwords need at least 8 characters.'
    return null
  }

  async function handleGoogleAuth() {
    setGoogleBusy(true)
    setError(null)
    try {
      const { idToken, displayName: gName } = await signInWithGoogle()
      const response = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ idToken, displayName: gName }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setError(body.detail ?? body.error ?? 'Google sign-in was not completed.')
        return
      }

      router.push(next as never)
      router.refresh()
    } catch (err: any) {
      if (
        err?.code === 'auth/popup-closed-by-user' ||
        err?.code === 'auth/cancelled-popup-request'
      ) {
        return
      }
      setError(err?.message ?? 'Could not sign in with Google. Try again.')
    } finally {
      setGoogleBusy(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()

    const problem = validate()
    if (problem) {
      setError(problem)
      return
    }

    setBusy(true)
    setError(null)

    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(
          isSignup ? { displayName, email, password } : { email, password },
        ),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setError(body.detail ?? body.error ?? 'That did not work. Try again.')
        return
      }

      router.push(next as never)
      router.refresh()
    } catch {
      setError('Could not reach the server. Check your connection and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="w-full max-w-[24rem]">
      <h1 className="font-serif text-display font-medium text-ink">
        {isSignup ? 'Create your account' : 'Welcome back'}
      </h1>
      <p className="mt-2 font-serif text-lead text-ink-soft">
        {isSignup
          ? 'Progress and code sync across the site and desktop app.'
          : 'Sign in to pick up where you left off.'}
      </p>

      {/* Google Sign-in Button */}
      <div className="mt-8">
        <button
          type="button"
          onClick={handleGoogleAuth}
          disabled={googleBusy || busy}
          className="inline-flex min-h-11 w-full items-center justify-center gap-3 rounded-field border border-rule-strong bg-paper px-4 text-caption font-medium text-ink transition-colors duration-200 ease-paper hover:bg-paper-raised disabled:opacity-60"
        >
          <svg className="size-4 shrink-0" viewBox="0 0 24 24" aria-hidden>
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>{googleBusy ? 'Connecting…' : 'Continue with Google'}</span>
        </button>
      </div>

      <div className="relative my-7 flex items-center justify-center">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-rule" />
        </div>
        <span className="relative bg-paper px-3 text-[12px] text-muted">
          or with email
        </span>
      </div>

      <form onSubmit={submit} className="space-y-6" noValidate>
        {isSignup && (
          <Field
            label="Name"
            value={displayName}
            onChange={setDisplayName}
            type="text"
            autoComplete="name"
          />
        )}
        <Field
          label="Email"
          value={email}
          onChange={setEmail}
          type="email"
          autoComplete="email"
        />
        <Field
          label="Password"
          value={password}
          onChange={setPassword}
          type="password"
          autoComplete={isSignup ? 'new-password' : 'current-password'}
          hint={isSignup ? 'At least 8 characters.' : undefined}
        />

        {error && (
          <p role="alert" className="text-caption text-fail">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || googleBusy}
          className="inline-flex min-h-11 w-full items-center justify-center rounded-field bg-ink px-5 text-caption font-medium text-paper transition-colors duration-200 ease-paper hover:bg-accent-deep disabled:opacity-60"
        >
          {busy ? 'Working…' : isSignup ? 'Create account' : 'Sign in'}
        </button>
      </form>

      <p className="mt-8 text-caption text-muted">
        {isSignup ? 'Already have an account? ' : 'New here? '}
        <Link
          href={isSignup ? '/login' : '/signup'}
          className="text-accent-deep underline decoration-1 underline-offset-4 transition-colors duration-200 ease-paper hover:text-ink"
        >
          {isSignup ? 'Sign in' : 'Create one'}
        </Link>
      </p>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  type,
  autoComplete,
  hint,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type: string
  autoComplete: string
  hint?: string
}) {
  const id = `field-${label.toLowerCase()}`
  const hintId = hint ? `${id}-hint` : undefined

  return (
    <div>
      <label htmlFor={id} className="block text-caption font-medium text-ink">
        {label}
      </label>
      {/* An underline rather than a box: a form on paper is a ruled line you
          write on. */}
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        aria-describedby={hintId}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-11 w-full border-b border-rule-strong bg-transparent pb-2 text-ink outline-none transition-colors duration-200 ease-paper focus:border-accent"
      />
      {hint && (
        <p id={hintId} className="mt-2 text-caption text-muted">
          {hint}
        </p>
      )}
    </div>
  )
}
