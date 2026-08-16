'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'

interface Props {
  mode: 'login' | 'signup'
  next: string
  localMode: boolean
}

/**
 * Sign in and sign up share every mechanic except one field and one endpoint,
 * so they share a component rather than drifting apart over time.
 */
export function AuthForm({ mode, next, localMode }: Props) {
  const isSignup = mode === 'signup'
  const router = useRouter()

  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function validate(): string | null {
    if (isSignup && displayName.trim().length === 0) return 'Enter the name you go by.'
    if (!email.includes('@')) return 'That email address is missing an @.'
    if (password.length < 8) return 'Passwords need at least 8 characters.'
    return null
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
    <div className="w-full max-w-[26rem]">
      <h1 className="text-title text-ink">
        {isSignup ? 'Create your account' : 'Welcome back'}
      </h1>
      <p className="mt-3 font-serif text-lead text-ink-soft">
        {isSignup
          ? 'Progress and code sync across the site and the desktop app.'
          : 'Sign in to pick up where you left off.'}
      </p>

      {localMode && (
        <p className="mt-6 border-l border-rule-strong pl-4 text-caption text-muted">
          This server is in local storage mode: accounts are saved to a JSON file on this
          machine, not a hosted database. Fine for trying things out. Set{' '}
          <code>SUPABASE_URL</code> and <code>SUPABASE_SERVICE_ROLE_KEY</code> for anything
          real.
        </p>
      )}

      <form onSubmit={submit} className="mt-9 space-y-6" noValidate>
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
          disabled={busy}
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
