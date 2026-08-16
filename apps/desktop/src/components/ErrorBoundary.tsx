import { Component, type ErrorInfo, type ReactNode } from 'react'

/**
 * Catches render errors and shows them.
 *
 * Without this, any throw during render unmounts the whole tree and a desktop
 * app becomes a black rectangle with no explanation and no devtools open. A
 * blank window is the least debuggable failure there is, so the app tells you
 * what broke instead.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  override state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[desktop] render failed', error, info.componentStack)
  }

  override render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex h-screen items-center justify-center bg-paper p-8">
        <div className="w-full max-w-2xl">
          <h1 className="text-lg font-semibold text-ink">The app failed to render</h1>
          <p className="mt-2 text-sm text-ink-soft">
            This is a bug. The error is below; the full stack is in the developer console.
          </p>

          <pre className="mt-5 max-h-80 overflow-auto rounded-lg border border-fail/30 bg-fail/5 p-4 text-xs leading-relaxed text-fail">
            {error.message}
            {error.stack ? `\n\n${error.stack}` : ''}
          </pre>

          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-5 rounded-field border border-rule bg-paper-raised px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-paper-sunken"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }
}
