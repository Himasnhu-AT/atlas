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
 * The one difference is in how the numbers are arrived at. The desktop parses
 * unittest's text, because a subprocess is all it has. Here the result object is
 * in hand, so the counts are read off it. Parsing "Ran 22 tests" when the number
 * is sitting in `res.testsRun` would be inventing an opportunity to be wrong.
 */

import { loadPyodide } from '/pyodide/pyodide.mjs'

let runtime = null

/**
 * Loaded once and kept. Starting it costs a few seconds and most of the
 * download; a student who runs their tests eleven times should pay that once.
 */
async function boot() {
  if (runtime) return runtime

  runtime = await loadPyodide({ indexURL: '/pyodide/' })
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

const RUNNER = `
import sys, io, importlib, unittest, traceback

def _run(directory):
    if directory in sys.path:
        sys.path.remove(directory)
    sys.path.insert(0, directory)

    # Every module the exercise owns, dropped so a second run sees the file the
    # student just edited rather than the one already imported. Without this the
    # first run is the only honest one.
    for name in [n for n, m in list(sys.modules.items())
                 if getattr(m, "__file__", None) and str(m.__file__).startswith(directory)]:
        del sys.modules[name]

    stream = io.StringIO()
    stdout, sys.stdout = sys.stdout, stream
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module("test"))
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        bad = len(result.failures) + len(result.errors)
        return {
            "ok": True,
            "testsTotal": result.testsRun,
            "testsPassed": result.testsRun - bad,
            "output": stream.getvalue(),
        }
    except BaseException:
        # An import-time error is the common one: a syntax error in the file the
        # student is editing. It is not a test failure and must not be reported
        # as though every test ran and failed.
        return {"ok": False, "testsTotal": 0, "testsPassed": 0,
                "output": stream.getvalue() + traceback.format_exc()}
    finally:
        sys.stdout = stdout
        if directory in sys.path:
            sys.path.remove(directory)
`

self.onmessage = async (event) => {
  const { id, files, solution } = event.data
  const started = Date.now()

  try {
    const py = await boot()
    const dir = '/exercise'

    // The student's buffer is always `solution.py`, the same fixed name the
    // desktop uses, because `test.py` imports from it.
    mount(py, dir, { ...files, 'solution.py': solution })

    py.runPython(RUNNER)
    const raw = py.globals.get('_run')(dir)
    const result = raw.toJs({ dict_converter: Object.fromEntries })
    raw.destroy()

    const testsTotal = result.testsTotal
    const testsPassed = result.testsPassed
    const output = String(result.output ?? '')

    self.postMessage({
      id,
      ok: true,
      // A run that could not import is not a pass, however few tests failed.
      passed: result.ok && testsTotal > 0 && testsPassed === testsTotal,
      testsPassed,
      testsTotal,
      durationMs: Date.now() - started,
      stdoutTail: output.slice(-4000),
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
