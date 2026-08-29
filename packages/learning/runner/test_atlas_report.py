"""
Tests for the shared report runner.

Every case here is one the old graders got wrong. A syntax error was reported
as every test failing on the desktop and as a suite of zero on the web; a
`setUpClass` failure shrank the denominator so "3 of 4" described a suite of
44; a `subTest` loop counted one missed condition four times. Each of those is
a test below.

Run with `python3 -m unittest discover -s runner -p 'test_*.py'` from
`packages/learning`.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atlas_report  # noqa: E402


class Fixture:
    """An exercise directory with a `solution.py` and a `test.py` in it."""

    def __init__(self, solution: str, test: str):
        self.dir = tempfile.mkdtemp(prefix="atlas-runner-")
        self._write("solution.py", solution)
        self._write("test.py", test)

    def _write(self, name: str, body: str) -> None:
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as handle:
            handle.write(body)

    def run(self) -> dict:
        return atlas_report.run(self.dir)

    def ids(self) -> list:
        return atlas_report.load_ids(self.dir)

    def close(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def by_id(report: dict) -> dict:
    return {t["id"]: t for t in report["tests"]}


class TestCleanRun(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(
            "def double(n):\n    return n * 2\n",
            "import unittest\n"
            "from solution import double\n"
            "\n"
            "class TestDouble(unittest.TestCase):\n"
            "    def test_doubles_two(self):\n"
            "        self.assertEqual(double(2), 4)\n"
            "\n"
            "    def test_doubles_zero(self):\n"
            "        self.assertEqual(double(0), 0)\n",
        )
        self.addCleanup(self.fixture.close)

    def test_reports_every_test_as_passed(self):
        report = self.fixture.run()
        self.assertEqual(report["kind"], "tests")
        self.assertEqual(report["testsTotal"], 2)
        self.assertEqual(report["testsPassed"], 2)
        self.assertEqual({t["status"] for t in report["tests"]}, {"passed"})

    def test_ids_are_class_dot_method_without_the_module(self):
        self.assertEqual(
            sorted(self.fixture.ids()),
            ["TestDouble.test_doubles_two", "TestDouble.test_doubles_zero"],
            "the case map is keyed on these, so the module prefix must be gone",
        )

    def test_load_ids_agrees_with_what_actually_ran(self):
        report = self.fixture.run()
        self.assertEqual(
            sorted(self.fixture.ids()),
            sorted(t["id"] for t in report["tests"]),
            "the build enforces map coverage against load_ids, so a drift here "
            "means a map that validates and never matches at runtime",
        )


class TestFailure(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(
            "def double(n):\n    return n + 2\n",
            "import unittest\n"
            "from solution import double\n"
            "\n"
            "class TestDouble(unittest.TestCase):\n"
            "    def test_doubles_two(self):\n"
            "        self.assertEqual(double(2), 4)\n"
            "\n"
            "    def test_doubles_three(self):\n"
            "        self.assertEqual(double(3), 6, 'adding is not doubling')\n",
        )
        self.addCleanup(self.fixture.close)

    def test_counts_the_one_that_passed_by_accident(self):
        report = self.fixture.run()
        self.assertEqual(report["testsTotal"], 2)
        self.assertEqual(report["testsPassed"], 1)

    def test_keeps_the_custom_assertion_message(self):
        record = by_id(self.fixture.run())["TestDouble.test_doubles_three"]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["exception"], "AssertionError")
        self.assertIn(
            "adding is not doubling",
            record["message"],
            "494 of the catalogue's tests carry this third argument and it is "
            "the closest thing to an authored condition they have",
        )

    def test_points_at_a_file_the_learner_can_open(self):
        record = by_id(self.fixture.run())["TestDouble.test_doubles_three"]
        self.assertIn(record["where"]["file"], {"test.py", "solution.py"})
        self.assertGreater(record["where"]["line"], 0)


class TestError(unittest.TestCase):
    def test_a_raise_is_an_error_not_a_failure(self):
        fixture = Fixture(
            "def double(n):\n    raise KeyError('nope')\n",
            "import unittest\n"
            "from solution import double\n"
            "\n"
            "class TestDouble(unittest.TestCase):\n"
            "    def test_doubles_two(self):\n"
            "        self.assertEqual(double(2), 4)\n",
        )
        self.addCleanup(fixture.close)
        record = by_id(fixture.run())["TestDouble.test_doubles_two"]
        self.assertEqual(record["status"], "error")
        self.assertEqual(record["exception"], "KeyError")


class TestSubTest(unittest.TestCase):
    def test_a_failing_subtest_loop_is_one_missed_condition(self):
        fixture = Fixture(
            "def positive(n):\n    return n > 1\n",
            "import unittest\n"
            "from solution import positive\n"
            "\n"
            "class TestPositive(unittest.TestCase):\n"
            "    def test_every_positive_number(self):\n"
            "        for n in (1, 2, 3):\n"
            "            with self.subTest(n=n):\n"
            "                self.assertTrue(positive(n))\n",
        )
        self.addCleanup(fixture.close)
        report = fixture.run()
        self.assertEqual(
            len(report["tests"]),
            1,
            "one method failing on three parameter sets is one row, not three, "
            "and the row's id has to match the case map key",
        )
        self.assertEqual(report["tests"][0]["id"], "TestPositive.test_every_positive_number")
        self.assertEqual(report["testsTotal"], 1)
        self.assertEqual(report["testsPassed"], 0)


class TestSetUpClassFailure(unittest.TestCase):
    def test_tests_that_never_ran_still_count_in_the_denominator(self):
        fixture = Fixture(
            "VALUE = 1\n",
            "import unittest\n"
            "\n"
            "class TestBroken(unittest.TestCase):\n"
            "    @classmethod\n"
            "    def setUpClass(cls):\n"
            "        raise RuntimeError('no fixture')\n"
            "\n"
            "    def test_one(self):\n"
            "        self.assertTrue(True)\n"
            "\n"
            "    def test_two(self):\n"
            "        self.assertTrue(True)\n",
        )
        self.addCleanup(fixture.close)
        report = fixture.run()
        self.assertEqual(
            report["testsTotal"],
            2,
            "unittest's own testsRun drops to 0 here, which would report a "
            "suite of 2 as a suite of 0",
        )
        self.assertEqual(report["testsPassed"], 0)
        self.assertEqual({t["status"] for t in report["tests"]}, {"not_run"})


class TestLoadError(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(
            "def double(n)\n    return n * 2\n",
            "import unittest\n"
            "from solution import double\n"
            "\n"
            "class TestDouble(unittest.TestCase):\n"
            "    def test_doubles_two(self):\n"
            "        self.assertEqual(double(2), 4)\n",
        )
        self.addCleanup(self.fixture.close)

    def test_a_syntax_error_is_not_every_test_failing(self):
        report = self.fixture.run()
        self.assertEqual(report["kind"], "load_error")
        self.assertEqual(report["testsTotal"], 0)
        self.assertEqual(report["tests"], [])

    def test_says_what_broke_and_where(self):
        error = self.fixture.run()["loadError"]
        self.assertEqual(error["exception"], "SyntaxError")
        self.assertTrue(error["message"])


class TestIsolation(unittest.TestCase):
    def test_a_second_run_sees_the_edited_solution(self):
        """
        The browser reuses one interpreter across runs, so a stale
        `sys.modules` entry would make the first run the only honest one.
        """
        fixture = Fixture(
            # n + 2 and n * 2 agree at n = 2, so the case has to be n = 3.
            "def double(n):\n    return n + 2\n",
            "import unittest\n"
            "from solution import double\n"
            "\n"
            "class TestDouble(unittest.TestCase):\n"
            "    def test_doubles_three(self):\n"
            "        self.assertEqual(double(3), 6)\n",
        )
        self.addCleanup(fixture.close)

        self.assertEqual(fixture.run()["testsPassed"], 0)
        fixture._write("solution.py", "def double(n):\n    return n * 2\n")
        self.assertEqual(
            fixture.run()["testsPassed"],
            1,
            "the fix was not picked up, so sys.modules was not purged",
        )

    def test_the_runner_leaves_sys_path_as_it_found_it(self):
        before = list(sys.path)
        fixture = Fixture(
            "X = 1\n",
            "import unittest\n"
            "\n"
            "class TestNothing(unittest.TestCase):\n"
            "    def test_true(self):\n"
            "        self.assertTrue(True)\n",
        )
        self.addCleanup(fixture.close)
        fixture.run()
        self.assertEqual(sys.path, before)


if __name__ == "__main__":
    unittest.main()
