/**
 * Typed wrappers over the Tauri commands exposed by `src-tauri`.
 *
 * Three invariants hold for everything in this file:
 *
 * 1. **Nothing calls `invoke` outside this module.** The rest of the app talks
 *    to Rust exclusively through these functions.
 * 2. **A Rust `Err(String)` becomes a thrown `Error`.** `invoke` rejects with
 *    the bare string; callers should be able to `catch (e) { e.message }`.
 * 3. **Calling one in a plain browser throws `DesktopUnavailableError` instead
 *    of exploding inside `@tauri-apps/api`.** `vite dev` in a browser is a
 *    supported way to work on this UI, so every command has a defined
 *    behaviour there.
 */

import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { isDesktop, type RunOutcome } from '@atlas/core'

/* -------------------------------------------------------------------- types */

/** One entry from `workspace_list`, normalised to camelCase. */
export interface FileEntry {
  name: string
  /** Path relative to the workspace root, `/`-separated. Feed straight back in. */
  path: string
  isDir: boolean
}

/** Payload of the `pty:output` event. */
export interface PtyOutput {
  id: string
  data: string
}

/** Payload of the `pty:exit` event, emitted once when a shell ends. */
export interface PtyExit {
  id: string
}

export const PTY_OUTPUT_EVENT = 'pty:output'
export const PTY_EXIT_EVENT = 'pty:exit'

/** Languages `run_exercise` knows how to execute. */
export type RunnableLanguage = 'python' | 'typescript' | 'bash'

/** Result of `run_tests`: the structured verdict behind a green or red run. */
export interface TestReport {
  passed: boolean
  testsPassed: number
  testsTotal: number
  durationMs: number
  /** Combined stdout and stderr, tail-truncated. */
  output: string
  /**
   * Set when the runner could not run at all, as opposed to tests failing.
   * A missing interpreter is not a red test, and the UI says so differently.
   */
  runnerError: string | null
  /**
   * The structured half: which tests, and what each one said.
   *
   * `testsPassed` and `testsTotal` above are copied out of this by the Rust
   * side, so the status bar and the results panel cannot disagree.
   */
  outcome: RunOutcome
}

/** One environment check from `preflight`. */
export interface PreflightCheck {
  name: string
  ok: boolean
  detail: string | null
  /** What to do about it. Present only when `ok` is false. */
  remedy: string | null
}

export interface PreflightReport {
  canRunExercises: boolean
  checks: PreflightCheck[]
  workspacePath: string | null
}

/** A directory the student granted the app access to. */
export interface Project {
  /** Absolute, canonicalized path. */
  path: string
  /** The directory's own name, for display. */
  name: string
}

/** One static-analysis finding. */
export interface Diagnostic {
  file: string
  line: number
  column: number
  severity: 'error' | 'warning'
  message: string
  /** Short kind: `syntax`, `undefined-name`, `stub`, `unused-import`, ... */
  rule: string
}

export interface AnalysisReport {
  /** False when at least one diagnostic is an error. */
  ok: boolean
  filesChecked: number
  diagnostics: Diagnostic[]
  durationMs: number
  /** Set when the analyser could not run at all, which is not a code defect. */
  runnerError: string | null
}

/* ------------------------------------------------------------------- errors */

/** Thrown when a desktop-only command is called from a plain browser tab. */
export class DesktopUnavailableError extends Error {
  readonly command: string

  constructor(command: string) {
    super(`\`${command}\` needs the desktop app — it is not available in the browser.`)
    this.name = 'DesktopUnavailableError'
    this.command = command
  }
}

function assertDesktop(command: string): void {
  if (!isDesktop()) throw new DesktopUnavailableError(command)
}

/**
 * Tauri rejects with whatever the command's `Err` variant serialises to, which
 * for every command here is a plain string. Turn that back into an `Error` so
 * callers have one thing to catch.
 */
function toError(cause: unknown, command: string): Error {
  if (cause instanceof Error) return cause
  if (typeof cause === 'string' && cause.trim() !== '') return new Error(cause)
  return new Error(`\`${command}\` failed.`, { cause })
}

/**
 * Arguments are serialised to JSON.
 *
 * `unknown` is admitted for the sync commands, whose payload is a whole request
 * body rather than a scalar. Everything else still passes scalars, and the
 * typed wrappers below are what actually constrain each command.
 */
type InvokeArgs = Record<string, string | number | boolean | null | unknown>

async function call<T>(command: string, args?: InvokeArgs): Promise<T> {
  assertDesktop(command)
  try {
    return await invoke<T>(command, args)
  } catch (cause) {
    throw toError(cause, command)
  }
}

/* ---------------------------------------------------------------------- pty */

/**
 * Open a shell in the workspace root and return its session id.
 * The size is the terminal's measured grid — pass the fitted values.
 */
export function ptySpawn(cols: number, rows: number): Promise<string> {
  return call<string>('pty_spawn', { cols: gridValue(cols), rows: gridValue(rows) })
}

/** Send raw bytes (usually keystrokes) to a session. */
export function ptyWrite(id: string, data: string): Promise<void> {
  return call<void>('pty_write', { id, data })
}

/** Tell the pty its window changed size, so `SIGWINCH`-aware programs reflow. */
export function ptyResize(id: string, cols: number, rows: number): Promise<void> {
  return call<void>('pty_resize', { id, cols: gridValue(cols), rows: gridValue(rows) })
}

/** Kill the shell and drop the session. Errors if the id is already gone. */
export function ptyKill(id: string): Promise<void> {
  return call<void>('pty_kill', { id })
}

/** Rust takes `u16`; clamp so a mid-layout measurement of 0 or NaN cannot panic. */
function gridValue(value: number): number {
  if (!Number.isFinite(value)) return 1
  return Math.min(Math.max(Math.floor(value), 1), 65_535)
}

/* ------------------------------------------------------------------- events */

/**
 * Subscribe to terminal output.
 *
 * Returns a synchronous unsubscribe so it drops straight into a `useEffect`
 * cleanup; the underlying `listen()` promise is settled internally, and a
 * teardown that happens before it resolves still detaches the listener.
 */
export function onPtyOutput(handler: (payload: PtyOutput) => void): () => void {
  return subscribe<PtyOutput>(PTY_OUTPUT_EVENT, handler)
}

/** Subscribe to session-ended notifications. Same contract as `onPtyOutput`. */
export function onPtyExit(handler: (payload: PtyExit) => void): () => void {
  return subscribe<PtyExit>(PTY_EXIT_EVENT, handler)
}

function subscribe<T>(event: string, handler: (payload: T) => void): () => void {
  if (!isDesktop()) return () => {}

  let unlisten: UnlistenFn | null = null
  let cancelled = false

  void listen<T>(event, (received) => {
    handler(received.payload)
  })
    .then((fn) => {
      if (cancelled) fn()
      else unlisten = fn
    })
    .catch((cause: unknown) => {
      console.warn(`[desktop] could not subscribe to \`${event}\``, cause)
    })

  return () => {
    cancelled = true
    unlisten?.()
    unlisten = null
  }
}

/* --------------------------------------------------------------- workspace */

/** Absolute path of the sandbox root. Created on first call. */
export function workspaceRoot(): Promise<string> {
  return call<string>('workspace_root')
}

/** List a directory inside the sandbox. `''` is the root. */
export async function workspaceList(rel: string): Promise<FileEntry[]> {
  const entries = await call<RawFileEntry[]>('workspace_list', { rel })
  return entries.map((entry) => ({
    name: entry.name,
    path: entry.path,
    // Rust serialises the flag under both casings; prefer camelCase, accept snake.
    isDir: entry.isDir ?? entry.is_dir ?? false,
  }))
}

/** Wire shape of `FileEntry` — the Rust side ships the directory flag twice. */
interface RawFileEntry {
  name: string
  path: string
  isDir?: boolean
  is_dir?: boolean
}

/** Read a UTF-8 text file from the sandbox. */
export function workspaceRead(rel: string): Promise<string> {
  return call<string>('workspace_read', { rel })
}

/** Write a text file into the sandbox, creating parent directories. */
export function workspaceWrite(rel: string, contents: string): Promise<void> {
  return call<void>('workspace_write', { rel, contents })
}

/* ------------------------------------------------------------------ runner */

/**
 * Run an exercise file by typing the command into an open terminal session,
 * so the learner keeps the shell (and history) they were already using.
 *
 * The file must already exist in the workspace — write the buffer first.
 */
export function runExercise(
  ptyId: string,
  language: RunnableLanguage,
  relPath: string,
): Promise<void> {
  return call<void>('run_exercise', { ptyId, language, relPath })
}

/**
 * Run an exercise's tests and get a structured verdict.
 *
 * Separate from `runExercise` because the two answer different questions. That
 * one gives the learner a shell they can poke at; this one gives the app a
 * pass or fail it can record as an attempt, plus the per-test detail the
 * results panel names conditions from. `output` is the raw runner text, which
 * the panel keeps behind a disclosure rather than echoing to the terminal.
 *
 * Never rejects for a failing test. A red suite is a successful call with
 * `passed: false`; only a broken environment sets `runnerError`.
 */
export function runTests(
  relDir: string,
  testFile: string,
  language: RunnableLanguage,
): Promise<TestReport> {
  return call<TestReport>('run_tests', { relDir, testFile, language })
}

/**
 * Check whether this machine can run exercises.
 *
 * Never rejects and never blocks: a failed check disables the Run button and
 * explains why, and reading a lesson keeps working regardless.
 */
export function preflight(): Promise<PreflightReport> {
  return call<PreflightReport>('preflight')
}

/* -------------------------------------------------------------- projects */

/**
 * Working on the student's own repository, rather than the app's sandbox.
 *
 * There is no `projectOpenPath(path)`. A root can only be granted through the
 * OS folder picker, which is what makes reaching outside the sandbox
 * legitimate: the student pointed at the directory themselves. Every call below
 * resolves its path against that granted root and cannot escape it.
 */

/**
 * Show the native folder picker and adopt the chosen directory.
 *
 * Resolves to `null` when the student cancels, which is not an error.
 */
export function projectOpen(): Promise<Project | null> {
  return call<Project | null>('project_open')
}

/** The currently granted project, restored across restarts. */
export function projectCurrent(): Promise<Project | null> {
  return call<Project | null>('project_current')
}

/** Give up access. The grant is forgotten on disk too. */
export function projectClose(): Promise<void> {
  return call<void>('project_close')
}

/** List a directory inside the project. `''` is the project root. */
export async function projectList(rel: string): Promise<FileEntry[]> {
  const entries = await call<RawFileEntry[]>('project_list', { rel })
  return entries.map((entry) => ({
    name: entry.name,
    path: entry.path,
    isDir: entry.isDir ?? entry.is_dir ?? false,
  }))
}

export function projectRead(rel: string): Promise<string> {
  return call<string>('project_read', { rel })
}

export function projectWrite(rel: string, contents: string): Promise<void> {
  return call<void>('project_write', { rel, contents })
}

/** Absolute path of the granted root, for the terminal's working directory. */
export function projectRoot(): Promise<string> {
  return call<string>('project_root')
}

/**
 * Statically check the project's Python: syntax, undefined names, stubs.
 *
 * No model is involved and nothing is executed, so this is safe to run on save
 * and finishes in well under a second on a normal repository. It answers
 * "will this run at all", not "is this any good": the second question needs a
 * live model, which is a separate and explicit step.
 *
 * Never rejects for finding problems. Diagnostics are a successful result;
 * `runnerError` is set only when the analysis itself could not happen.
 */
export function projectAnalyse(rel = ''): Promise<AnalysisReport> {
  return call<AnalysisReport>('project_analyse', { rel })
}

/* --------------------------------------------------------------------- auth */

/**
 * Who is signed in.
 *
 * Deliberately never includes the token. It lives in a file Rust owns, and the
 * requests that need it are made in Rust, so the webview has no reason to hold
 * a thirty-day bearer credential and does not.
 */
export interface Account {
  email: string
  displayName: string
  apiBase: string
}

export function authAccount(): Promise<Account | null> {
  return call<Account | null>('auth_account')
}

export function authClear(): Promise<void> {
  return call<void>('auth_clear')
}

/* --------------------------------------------------------------------- sync */

export interface Pending {
  count: number
  signedIn: boolean
}

export interface DrainResult {
  /** `idle` nothing queued · `signed-out` no account · `synced` · `unauthorized`. */
  status: 'idle' | 'signed-out' | 'synced' | 'unauthorized'
  sent: number
  accepted: number
  dropped: number
  awarded: number
  remaining: number
  game?: unknown
  detail?: string
}

export interface PairStart {
  userCode: string
  verificationUriComplete: string
  intervalSeconds: number
  deviceCode: string
}

export interface PairPoll {
  status: 'pending' | 'expired' | 'approved'
  account: Account | null
}

/**
 * Queue an event for the server.
 *
 * The payload is the body of the route it names, so the outbox is those calls
 * made durable rather than a second wire format. Returns the client event id,
 * which is what makes a replay of the same batch harmless.
 */
export function syncQueue(kind: string, payload: unknown): Promise<string> {
  return call<string>('sync_queue', { kind, payload })
}

export function syncPending(): Promise<Pending> {
  return call<Pending>('sync_pending')
}

export function syncDrain(): Promise<DrainResult> {
  return call<DrainResult>('sync_drain')
}

export function syncPairStart(name: string, platform: string): Promise<PairStart> {
  return call<PairStart>('sync_pair_start', { name, platform })
}

export function syncPairPoll(deviceCode: string): Promise<PairPoll> {
  return call<PairPoll>('sync_pair_poll', { deviceCode })
}
