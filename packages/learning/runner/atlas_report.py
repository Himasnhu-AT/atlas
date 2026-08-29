"""
One test run, as a machine-readable result.

Both graders use this file. The desktop passes it to `python3 -c`; the browser
worker fetches it and hands it to Pyodide. That is what makes "exercises grade
in two places and must mean the same thing in both" a fact about one file
rather than a promise about two.

Nothing here parses unittest's text output. The result object is in hand in
both places, so the counts and the failures are read off it. The text is still
produced, unchanged, because the learner is shown it verbatim and a runner that
quietly altered what `python3 test.py` looks like would be worse than one that
reported nothing.

Stdlib only, Python 3.10+. The shape it emits is `RunOutcome` in
`packages/core/src/grading.ts`.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import time
import traceback
import unittest

MAX_REPORTED_TESTS = 120
MAX_MESSAGE_CHARS = 300
MAX_TEST_ID_CHARS = 120

# Files a learner owns or can read. A frame in one of these is worth pointing
# at; a frame inside unittest is not.
OWNED_FILES = frozenset({"solution.py", "test.py"})


def _identify(test):
    """
    Return `(id, is_holder)` for whatever unittest just handed us.

    Three shapes arrive here. A TestCase, which is the normal one. A `_SubTest`,
    which wraps a TestCase and whose own `id()` carries the parameters: four
    failing subtests are one missed condition, so they collapse onto the case
    they came from. And an `_ErrorHolder`, which is what a `setUpClass` failure
    looks like: not a test, no method name, and the reason none of a class's
    tests ran.
    """
    inner = getattr(test, "test_case", test)
    method = getattr(inner, "_testMethodName", None)
    if method:
        return f"{type(inner).__name__}.{method}"[:MAX_TEST_ID_CHARS], False
    described = getattr(test, "description", None) or test.id()
    return str(described)[:MAX_TEST_ID_CHARS], True


def _frame(tb):
    """The deepest frame in a file the learner owns, or None."""
    found = None
    for entry in traceback.extract_tb(tb):
        if os.path.basename(entry.filename) in OWNED_FILES:
            found = {"file": os.path.basename(entry.filename), "line": entry.lineno or 0}
    return found


def _flatten(suite):
    """Every real test in a suite, in declaration order, holders excluded."""
    ids = []
    stack = [suite]
    while stack:
        item = stack.pop(0)
        if isinstance(item, unittest.TestSuite):
            stack = list(item) + stack
        else:
            key, holder = _identify(item)
            if not holder:
                ids.append(key)
    return ids


class _Collector(unittest.TextTestResult):
    """A result that keeps the failure objects instead of only formatting them."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = {}
        self.started = {}
        self.elapsed = {}

    def startTest(self, test):
        super().startTest(test)
        key, _ = _identify(test)
        self.started[key] = time.perf_counter()

    def stopTest(self, test):
        super().stopTest(test)
        key, _ = _identify(test)
        begun = self.started.get(key)
        if begun is not None and key not in self.elapsed:
            self.elapsed[key] = int((time.perf_counter() - begun) * 1000)

    def _record(self, test, err, status):
        key, holder = _identify(test)
        if key in self.records:
            # First failure wins. A subTest loop that fails on three parameter
            # sets is one condition the learner missed, reported once.
            return
        kind, value, tb = err
        self.records[key] = {
            "id": key,
            "status": "error" if holder else status,
            "exception": getattr(kind, "__name__", str(kind))[:80],
            "message": str(value)[:MAX_MESSAGE_CHARS],
            "where": _frame(tb),
        }

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, err, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, err, "error")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(subtest, err, "failed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        key, _ = _identify(test)
        self.records.setdefault(
            key,
            {"id": key, "status": "skipped", "message": str(reason)[:MAX_MESSAGE_CHARS]},
        )

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        key, _ = _identify(test)
        self.records.setdefault(
            key,
            {"id": key, "status": "failed", "message": "passed, but was expected to fail"},
        )


def _prepare(directory):
    """
    Make `directory` the first place Python looks, and forget what it saw there
    last time.

    The purge matters only in the browser, where one interpreter serves every
    run: without it, the first run would be the only honest one. It is a no-op
    in a fresh subprocess, and it lives here so both graders do the same thing
    rather than one of them doing it correctly.

    `insert(0, ...)` rather than `append`: the exercise's `test` module has to
    win against anything of that name already importable.
    """
    # Never leave a __pycache__ in the learner's exercise directory. The
    # content build hashes every file in there to decide whether the exercise
    # moved underneath their work, and the desktop already passes
    # PYTHONDONTWRITEBYTECODE for the same reason.
    sys.dont_write_bytecode = True

    while directory in sys.path:
        sys.path.remove(directory)
    sys.path.insert(0, directory)

    # Two ways a stale module survives into this run, and both have to go.
    #
    # By path: something imported from this directory last time. That is the
    # ordinary case, a learner re-running after an edit.
    #
    # By name: `solution` or `test` cached from a DIFFERENT directory, which
    # happens the moment one interpreter serves two exercises. `startswith`
    # alone does not catch it, and the failure is silent and total: the suite
    # imports cleanly and grades the previous exercise's code.
    local = {
        entry[:-3]
        for entry in os.listdir(directory)
        if entry.endswith(".py") and not entry.startswith(".")
    }
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if name.split(".")[0] in local or (path and str(path).startswith(directory)):
            del sys.modules[name]

    # Forgetting the module is not enough. The finders cache directory listings,
    # and a cached .pyc is trusted on matching size and mtime, so a one
    # character edit made in the same second as the last run is loaded from
    # bytecode that no longer matches the source. That is not an edge case: it
    # is a learner fixing a typo and running again.
    importlib.invalidate_caches()


def load_ids(directory, test_module="test"):
    """
    Every test the loader finds, in declaration order.

    The content build calls this to know what an exercise's case map has to
    cover. The loader is the ground truth rather than an AST walk, so
    inheritance, mixins and `load_tests` are handled by the thing that will
    actually run them, and the build's idea of a test id cannot drift from the
    runner's.
    """
    _prepare(directory)
    suite = unittest.defaultTestLoader.loadTestsFromModule(
        importlib.import_module(test_module)
    )
    return _flatten(suite)


def run(directory, test_module="test"):
    """
    Run one exercise's tests and describe the result.

    Never raises. A suite that will not import is a `load_error`, which is a
    different thing from every test failing and must never be reported as one:
    a learner with a missing colon on line 12 has not failed 44 conditions.
    """
    stream = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = stream
    try:
        try:
            _prepare(directory)
            module = importlib.import_module(test_module)
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            loaded = _flatten(suite)
        except BaseException:
            kind, value, tb = sys.exc_info()
            frame = _frame(tb) or {}
            return {
                "kind": "load_error",
                "testsTotal": 0,
                "testsPassed": 0,
                "tests": [],
                "truncated": False,
                "loadError": {
                    "exception": getattr(kind, "__name__", "Error")[:80],
                    "message": str(value)[:MAX_MESSAGE_CHARS],
                    **frame,
                },
                "output": stream.getvalue() + traceback.format_exc(),
            }

        runner = unittest.TextTestRunner(
            stream=stream, verbosity=2, resultclass=_Collector
        )
        result = runner.run(suite)

        tests = []
        for key in loaded:
            record = result.records.get(key)
            if record is None:
                # Loaded and no verdict recorded. Either it passed, or
                # `setUpClass` stopped it before it ever started.
                record = {
                    "id": key,
                    "status": "passed" if key in result.started else "not_run",
                }
            if key in result.elapsed:
                record.setdefault("durationMs", result.elapsed[key])
            tests.append({k: v for k, v in record.items() if v is not None})

        bad = sum(1 for t in tests if t["status"] in ("failed", "error", "not_run"))
        return {
            "kind": "tests",
            "testsTotal": len(loaded),
            "testsPassed": len(loaded) - bad,
            "tests": tests[:MAX_REPORTED_TESTS],
            "truncated": len(tests) > MAX_REPORTED_TESTS,
            "output": stream.getvalue(),
        }
    finally:
        sys.stdout = real_stdout
        while directory in sys.path:
            sys.path.remove(directory)


def _main():
    """
    The desktop entry point.

    Both inputs come from the environment rather than from `sys.argv`, so the
    program text the interpreter receives stays a compile-time constant in the
    Rust binary and nothing a caller supplies is ever formatted into it.
    """
    directory = os.environ.get("ATLAS_EXERCISE_DIR") or os.getcwd()
    module = os.environ.get("ATLAS_TEST_MODULE", "test")
    report = run(os.path.abspath(directory), module)
    output = report.pop("output", "")
    with open(os.environ["ATLAS_REPORT_PATH"], "w", encoding="utf-8") as handle:
        json.dump(report, handle)
    # The learner is shown this verbatim, so it goes where it always went.
    sys.stderr.write(output)
    passed = report["kind"] == "tests" and report["testsPassed"] == report["testsTotal"]
    return 0 if passed else 1


# Guarded on the variable rather than on `__name__`. Pyodide's `runPython`
# executes this in `__main__` too, and the browser wants the functions defined,
# not a run started.
if os.environ.get("ATLAS_REPORT_PATH"):
    raise SystemExit(_main())
