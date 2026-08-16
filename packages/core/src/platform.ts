/**
 * Which shell the shared code is running inside.
 *
 * Both apps import the same components, and a few of them behave differently on
 * desktop: the practice pane only exists there, and a lesson's exercise links
 * into the editor rather than prompting for a download.
 */

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown
  }
}

export function isDesktop(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

export function isBrowser(): boolean {
  return typeof window !== 'undefined' && !isDesktop()
}

/** True during server rendering, where neither of the above applies. */
export function isServer(): boolean {
  return typeof window === 'undefined'
}
