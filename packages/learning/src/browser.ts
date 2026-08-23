/**
 * Which exercises can be graded in a browser, decided at build time.
 *
 * The web app runs CPython compiled to WebAssembly, which is the same
 * interpreter running the same `unittest` against the same course library, with
 * no server and no API key. That covers almost the whole catalogue.
 *
 * It does not cover all of it, and the failure mode is why this is a build-time
 * declaration rather than a runtime attempt. `parallel-dispatch` imports
 * `threading`; under the browser runtime its own reference solution fails 15 of
 * its 24 tests, because the runtime has no threads to give and the calls raise
 * rather than the import. A student would see a red suite and conclude their
 * correct code was wrong, which is worse than being told up front to use the
 * desktop app. So the browser never offers to run what it cannot grade.
 */

/**
 * Modules that do not work under the browser runtime.
 *
 * `threading` and `concurrent` are measured: probed against Pyodide 314, both
 * raise `RuntimeError: can't start new thread`. The rest are structural, in that
 * a browser sandbox has no processes and no sockets to give them.
 *
 * `sqlite3` is deliberately absent. It was the other candidate and it works, so
 * the whole data engineering course grades in a browser.
 */
export const BROWSER_UNSUPPORTED: Record<string, string> = {
  threading: 'the browser runtime cannot start threads',
  concurrent: 'the browser runtime cannot start threads',
  multiprocessing: 'the browser runtime has no processes',
  subprocess: 'the browser runtime cannot start processes',
  socket: 'the browser runtime has no sockets',
}

export interface BrowserSupport {
  runnable: boolean
  /** Why not, in a form a lesson page can show a student. Absent when runnable. */
  reason?: string
}

/**
 * Reads the top-level imports of one Python source file.
 *
 * Deliberately a regex over line starts rather than a parse. It only has to see
 * imports that actually execute, and one anchored at column zero is exactly
 * that: an indented import inside a function is already inside code the test
 * either runs or does not. Prose in a docstring cannot match, because a
 * docstring's lines are indented under the def they belong to, and a module
 * docstring's are not import statements.
 */
export function topLevelImports(source: string): string[] {
  const found = new Set<string>()
  for (const line of source.split('\n')) {
    const match = /^(?:import|from)\s+([A-Za-z_][\w.]*)/.exec(line)
    if (match) found.add(match[1]!.split('.')[0]!)
  }
  return [...found]
}

/**
 * Whether an exercise can be graded in a browser, given its shipped files.
 *
 * Reads the test and the scaffold, not the reference. The test is what runs, and
 * the scaffold is what the student starts from; a reference that reached for
 * threads while the test did not would still grade correctly.
 */
export function browserSupportFor(files: Record<string, string>): BrowserSupport {
  const blocked = new Set<string>()

  for (const [name, source] of Object.entries(files)) {
    if (!name.endsWith('.py')) continue
    if (name === 'reference.py') continue
    for (const module of topLevelImports(source)) {
      if (module in BROWSER_UNSUPPORTED) blocked.add(module)
    }
  }

  if (blocked.size === 0) return { runnable: true }

  const [first] = [...blocked].sort()
  return { runnable: false, reason: BROWSER_UNSUPPORTED[first!]! }
}
