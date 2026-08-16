/**
 * Makes a failed start visible.
 *
 * This has to be its own module, imported first by `main.tsx`, for two reasons
 * that are easy to get wrong:
 *
 * 1. **Handlers registered inside `main.tsx` are too late.** ES module imports
 *    are evaluated before any statement in the importing module runs, so a
 *    module-level throw anywhere in the graph happens before such a handler
 *    exists. That is exactly the case that produces a blank window, and exactly
 *    the case it would fail to report.
 * 2. **It cannot be an inline `<script>` in index.html.** Tauri's CSP is
 *    `script-src 'self'` with no `unsafe-inline`, so an inline script is
 *    blocked outright.
 *
 * A desktop window that fails silently is the least debuggable thing there is:
 * no console is open, no terminal shows the renderer, and the app looks merely
 * broken rather than broken *for a reason*. This prints the reason on the page.
 */

const ROOT_ID = 'root'

function show(cause: unknown): void {
  const root = document.getElementById(ROOT_ID)
  // Something already rendered, so this is a later error, not a failed start.
  // React's error boundary owns that case and reports it in context.
  if (!root || root.childElementCount > 0) return

  const message =
    cause instanceof Error ? (cause.stack ?? cause.message) : String(cause)

  const pre = document.createElement('pre')
  pre.style.cssText = [
    'margin:0',
    'padding:2rem',
    'font:13px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace',
    'color:#9c3328',
    'background:#f7f4ee',
    'white-space:pre-wrap',
    'word-break:break-word',
    'min-height:100vh',
  ].join(';')
  pre.textContent = `The app failed to start.\n\n${message}`

  root.replaceChildren(pre)
}

window.addEventListener('error', (event) => show(event.error ?? event.message))
window.addEventListener('unhandledrejection', (event) => show(event.reason))
