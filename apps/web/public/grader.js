/**
 * The browser grader: one exercise, one verdict, off the main thread.
 *
 * A module worker loaded from `public/` rather than a bundled one, because the
 * runtime it pulls in is a 13 MB same-origin asset that no bundler should be
 * asked to reason about. It has to be a module worker: `importScripts` is
 * refused outright in some browsers now, and the failure arrives as "classic web
 * workers are not supported" at the moment a student clicks Run.
 *
 * The contract matches the desktop grader's exactly: how many tests ran, how
 * many passed, how long it took, and the tail of the output. The same
 * `/api/attempts` route accepts both, so where a student practised changes what
 * it felt like and nothing about what it was worth.
 *
 * There is no longer a difference in how the numbers are arrived at. Both
 * graders run `packages/learning/runner/atlas_report.py`, which reads the
 * unittest result object rather than its text. This worker fetches that file;
 * the desktop compiles it in. That is what makes "grade in two places and mean
 * the same thing in both" a fact about one file rather than a promise about
 * two.
 */

import { loadPyodide } from '/pyodide/pyodide.mjs'

let runtime = null

/**
 * Loaded once and kept. Starting it costs a few seconds and most of the
 * download; a student who runs their tests eleven times should pay that once.
 */
async function boot() {
  if (runtime) return runtime

  // Copied into `public/` by `scripts/copy-runner.mjs` at predev and prebuild,
  // the same way the interpreter is, so there is one source for it and not a
  // second copy to keep in step.
  const [py, source] = await Promise.all([
    loadPyodide({ indexURL: '/pyodide/' }),
    fetch('/atlas_report.py').then((response) => {
      if (!response.ok) throw new Error(`could not load the test runner (${response.status})`)
      return response.text()
    }),
  ])

  py.runPython(source)
  runtime = py
  return runtime
}

/** Everything the exercise ships, written where Python will find it. */
function mount(py, dir, files) {
  try {
    py.FS.mkdir(dir)
  } catch {
    // Already there from an earlier run in this session.
  }
  for (const [name, source] of Object.entries(files)) {
    if (name.endsWith('.py')) py.FS.writeFile(`${dir}/${name}`, source)
  }
}


self.onmessage = async (event) => {
  const { id, files, solution } = event.data
  const started = Date.now()

  try {
    const py = await boot()
    const dir = '/exercise'

    // The student's buffer is always `solution.py`, the same fixed name the
    // desktop uses, because `test.py` imports from it.
    mount(py, dir, { ...files, 'solution.py': solution })

    const raw = py.globals.get('run')(dir)
    const report = raw.toJs({ dict_converter: Object.fromEntries })
    raw.destroy()

    const output = String(report.output ?? '')
    delete report.output

    self.postMessage({
      id,
      ok: true,
      // A run that could not import is not a pass, however few tests failed.
      passed:
        report.kind === 'tests' &&
        report.testsTotal > 0 &&
        report.testsPassed === report.testsTotal,
      testsPassed: report.testsPassed,
      testsTotal: report.testsTotal,
      durationMs: Date.now() - started,
      stdoutTail: output.slice(-4000),
      // The structured half: which tests, and what each one said. This is what
      // lets the page name the conditions the learner did not account for
      // instead of printing four kilobytes of unittest at them.
      outcome: report,
    })
  } catch (error) {
    self.postMessage({
      id,
      ok: false,
      message: String((error && error.message) || error),
      durationMs: Date.now() - started,
    })
  }
}
