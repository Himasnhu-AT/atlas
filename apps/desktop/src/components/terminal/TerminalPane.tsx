import { useEffect, useImperativeHandle, useRef, type Ref } from 'react'
import { Terminal, type ITheme } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { isDesktop } from '@atlas/core'
import { cn } from '@atlas/ui'
import {
  onPtyExit,
  onPtyOutput,
  ptyKill,
  ptyResize,
  ptySpawn,
  ptyWrite,
  type PtyOutput,
} from '../../lib/ipc'

/** One Dark / One Light, matching the CodeMirror themes in the editor pane. */
/**
 * The terminal, set on paper.
 *
 * The background matches the lesson's code blocks rather than the page, so a
 * listing and a shell read as the same kind of object. ANSI colours are taken
 * down in chroma to sit on a warm ground: the saturated defaults look like a
 * different application pasted into the window.
 */
const TERMINAL_THEME: ITheme = {
  background: '#f2eee6',
  foreground: '#3a352d',
  cursor: '#2d4a72',
  cursorAccent: '#f2eee6',
  selectionBackground: '#dcd5c6',
  black: '#3a352d',
  red: '#9c3328',
  green: '#2f6b46',
  yellow: '#8a6218',
  blue: '#2d4a72',
  magenta: '#6b3f6e',
  cyan: '#2b6a70',
  white: '#c4bbaa',
  brightBlack: '#6d6558',
  brightRed: '#b8422f',
  brightGreen: '#3a7f54',
  brightYellow: '#a2761f',
  brightBlue: '#3a5c8a',
  brightMagenta: '#815085',
  brightCyan: '#357f86',
  brightWhite: '#1a1714',
}

/** How long the container has to stay still before we re-fit and tell the pty. */
const RESIZE_DEBOUNCE_MS = 80
/** Caps on what is held while the session is starting, so a stall cannot grow without bound. */
const MAX_PENDING_INPUT = 256
const MAX_EARLY_OUTPUT = 256

export interface TerminalPaneHandle {
  /** Move keyboard focus into the terminal. */
  focus: () => void
  /** Clear the viewport, keeping the shell running. */
  clear: () => void
  /** Print text locally. Does not send anything to the shell. */
  write: (data: string) => void
  /** Live pty session id, or `null` before it spawns / after it dies. */
  readonly sessionId: string | null
}

export interface TerminalPaneProps {
  ref?: Ref<TerminalPaneHandle>
  className?: string
  /** Focus the terminal as soon as the session is live. */
  autoFocus?: boolean
  /** Called with the session id when it opens, and with `null` when it closes. */
  onSessionChange?: (sessionId: string | null) => void
  /** Called when the session could not be created or died unexpectedly. */
  onError?: (message: string) => void
}

function messageOf(error: unknown): string {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  return String(error)
}

/**
 * Embedded terminal wired to the Rust pty commands.
 *
 * The whole lifecycle — terminal, addons, event subscription, ResizeObserver and
 * the pty session itself — is owned by one effect, so React's StrictMode
 * double-mount tears everything down and rebuilds it symmetrically. `pty_spawn`
 * is asynchronous, so every continuation re-checks the `disposed` flag captured
 * by that effect run and kills the session it just created if the effect has
 * already been cleaned up; `killSession` is idempotent, so the cleanup path and
 * the late-resolve path can never double-kill.
 *
 * The pane fills its parent absolutely and the ResizeObserver watches the outer
 * box only, so `fit()` can never change what the observer measures — no resize
 * feedback loop.
 */
export function TerminalPane({
  ref,
  className,
  autoFocus = false,
  onSessionChange,
  onError,
}: TerminalPaneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const termRef = useRef<Terminal | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const autoFocusRef = useRef(autoFocus)
  const onSessionChangeRef = useRef(onSessionChange)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    autoFocusRef.current = autoFocus
    onSessionChangeRef.current = onSessionChange
    onErrorRef.current = onError
  })

  useImperativeHandle(
    ref,
    () => ({
      focus: () => termRef.current?.focus(),
      clear: () => termRef.current?.clear(),
      write: (data: string) => termRef.current?.write(data),
      get sessionId() {
        return sessionIdRef.current
      },
    }),
    [],
  )

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    let disposed = false
    let sessionId: string | null = null
    let killed = false
    let observer: ResizeObserver | null = null
    let resizeTimer: number | null = null
    // Sizes already pushed to the pty; -1 forces the first push through.
    let sentCols = -1
    let sentRows = -1
    // Keystrokes typed before the session is live, replayed once it is.
    const pendingInput: string[] = []
    // Output that arrived before `pty_spawn` resolved and told us our id.
    let earlyOutput: PtyOutput[] = []

    const term = new Terminal({
      allowProposedApi: false,
      convertEol: false,
      cursorBlink: true,
      drawBoldTextInBrightColors: true,
      // A literal stack (not `var(--font-mono)`): xterm measures cell size with
      // this string, and a CSS variable does not resolve in that measurement.
      // Kept in step with the `--font-mono` token in @atlas/ui.
      fontFamily:
        '"JetBrains Mono", "SFMono-Regular", ui-monospace, Menlo, Consolas, "Liberation Mono", monospace',
      fontSize: 13,
      lineHeight: 1.2,
      macOptionIsMeta: true,
      scrollback: 5000,
      theme: TERMINAL_THEME,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(host)
    termRef.current = term

    const fail = (error: unknown) => {
      const message = messageOf(error)
      if (!disposed) term.writeln(`\r\n\x1b[31m${message}\x1b[0m`)
      onErrorRef.current?.(message)
    }

    const killSession = (id: string) => {
      if (killed) return
      killed = true
      void ptyKill(id).catch(() => {
        // The shell may already be gone; nothing left to clean up.
      })
    }

    /** Re-measure. Returns false when the pane is not laid out (hidden/zero-size). */
    const refit = (): boolean => {
      if (fitAddon.proposeDimensions() === undefined) return false
      fitAddon.fit()
      return true
    }

    const pushSize = () => {
      if (disposed || killed || !sessionId) return
      if (term.cols === sentCols && term.rows === sentRows) return
      sentCols = term.cols
      sentRows = term.rows
      void ptyResize(sessionId, term.cols, term.rows).catch(fail)
    }

    refit()

    const dataSub = term.onData((chunk) => {
      if (disposed || killed) return
      if (!sessionId) {
        if (pendingInput.length < MAX_PENDING_INPUT) pendingInput.push(chunk)
        return
      }
      void ptyWrite(sessionId, chunk).catch(fail)
    })

    // Subscribed before `pty_spawn` is even called: the shell can print its
    // prompt before the spawn promise resolves, and an event emitted before we
    // are listening is gone for good. Anything that arrives while our id is
    // still unknown is held here and replayed once we know it.
    const stopOutput = onPtyOutput((event) => {
      if (disposed) return
      if (sessionId === null) {
        if (earlyOutput.length < MAX_EARLY_OUTPUT) earlyOutput.push(event)
        return
      }
      if (event.id !== sessionId) return
      term.write(event.data)
    })

    const stopExit = onPtyExit((event) => {
      if (disposed || sessionId === null || event.id !== sessionId) return
      // The shell ended on its own: the backend has already dropped the
      // session, so nothing may be written to it again.
      killed = true
      sessionId = null
      sessionIdRef.current = null
      term.writeln('\r\n\x1b[2m[shell exited]\x1b[0m')
      onSessionChangeRef.current?.(null)
    })

    observer = new ResizeObserver(() => {
      if (resizeTimer !== null) window.clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => {
        resizeTimer = null
        if (disposed) return
        if (refit()) pushSize()
      }, RESIZE_DEBOUNCE_MS)
    })
    observer.observe(host)

    if (!isDesktop()) {
      // Browser preview (`pnpm dev:web`): no Tauri, so no pty. Say so instead of
      // failing invisibly, and never touch `invoke`.
      term.writeln('\x1b[33mThe embedded terminal only runs in the desktop app.\x1b[0m')
      term.writeln('Start it with \x1b[1mpnpm --filter @atlas/desktop dev\x1b[0m.')
    } else {
      void (async () => {
        try {
          const id = await ptySpawn(term.cols, term.rows)
          // StrictMode (or a fast unmount) can retire this effect run while the
          // spawn is still in flight. The session exists now, so kill it rather
          // than leak a shell nobody is listening to.
          if (disposed) {
            killSession(id)
            return
          }

          sessionId = id
          sessionIdRef.current = id
          sentCols = term.cols
          sentRows = term.rows

          for (const event of earlyOutput) {
            if (event.id === id) term.write(event.data)
          }
          earlyOutput = []

          onSessionChangeRef.current?.(id)

          if (pendingInput.length > 0) {
            const buffered = pendingInput.join('')
            pendingInput.length = 0
            void ptyWrite(id, buffered).catch(fail)
          }
          // The pane may have been resized while the shell was starting.
          if (refit()) pushSize()
          if (autoFocusRef.current) term.focus()
        } catch (error) {
          if (!disposed) fail(error)
        }
      })()
    }

    return () => {
      disposed = true
      if (resizeTimer !== null) {
        window.clearTimeout(resizeTimer)
        resizeTimer = null
      }
      observer?.disconnect()
      observer = null
      stopOutput()
      stopExit()
      dataSub.dispose()
      earlyOutput = []
      if (sessionId) {
        killSession(sessionId)
        sessionId = null
        sessionIdRef.current = null
        onSessionChangeRef.current?.(null)
      }
      fitAddon.dispose()
      term.dispose()
      termRef.current = null
    }
  }, [])


  return (
    <div
      // Read from TERMINAL_THEME rather than restated as a class, so this box
      // and the character grid cannot drift apart. It is what shows in the
      // gutter xterm leaves around the grid, and before the first paint.
      style={{ backgroundColor: TERMINAL_THEME.background }}
      className={cn('relative h-full min-h-0 w-full overflow-hidden', className)}
    >
      {/* Absolutely positioned so its box is driven purely by the parent: the
          ResizeObserver above can never observe a size that `fit()` produced. */}
      <div ref={hostRef} className="absolute inset-0 p-2" />
    </div>
  )
}
