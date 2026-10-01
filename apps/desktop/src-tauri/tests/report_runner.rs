//! The desktop's actual invocation of the shared test runner.
//!
//! The unit tests in `grader.rs` prove that a report parses. This proves that
//! running `python3 -c <the compiled-in runner>` with the two environment
//! variables produces one, which is the half that the old string-scraping
//! grader got wrong and that no amount of JSON fixture testing would catch.
//!
//! Skipped when there is no `python3` on PATH, so the suite still runs on a
//! machine that cannot host the desktop app anyway.

use std::fs;
use std::process::Command;

const REPORT_RUNNER: &str = include_str!("../../../../packages/learning/runner/atlas_report.py");

fn python3_available() -> bool {
    Command::new("python3")
        .arg("--version")
        .output()
        .map(|out| out.status.success())
        .unwrap_or(false)
}

/// Run the runner the way `grader.rs` does, and return the parsed report.
fn run_fixture(solution: &str, test: &str) -> serde_json::Value {
    let dir = tempfile::tempdir().unwrap();
    fs::write(dir.path().join("solution.py"), solution).unwrap();
    fs::write(dir.path().join("test.py"), test).unwrap();

    let report = dir.path().join("report.json");
    let output = Command::new("python3")
        .arg("-c")
        .arg(REPORT_RUNNER)
        .current_dir(dir.path())
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("ATLAS_EXERCISE_DIR", dir.path())
        .env("ATLAS_TEST_MODULE", "test")
        .env("ATLAS_REPORT_PATH", &report)
        .output()
        .expect("python3 should start");

    // unittest's text still reaches the learner, unchanged.
    let text = String::from_utf8_lossy(&output.stderr);
    assert!(
        text.contains("Ran ") || text.contains("Traceback"),
        "the runner stopped producing the output the learner is shown: {text}"
    );

    serde_json::from_str(&fs::read_to_string(&report).expect("a report should have been written"))
        .expect("the report should be JSON")
}

const PASSING: &str = "def double(n):\n    return n * 2\n";
const BROKEN: &str = "def double(n):\n    return n + 2\n";

// A raw string, because a `\`-continued Rust literal strips the leading
// whitespace of each continuation line, which silently un-indents Python and
// turns every fixture into an IndentationError.
const SUITE: &str = r#"
import unittest

from solution import double


class TestDouble(unittest.TestCase):
    def test_doubles_two(self):
        self.assertEqual(double(2), 4)

    def test_doubles_three(self):
        self.assertEqual(double(3), 6, "adding is not doubling")
"#;

#[test]
fn a_clean_run_reports_every_test_passing() {
    if !python3_available() {
        return;
    }
    let report = run_fixture(PASSING, SUITE);
    assert_eq!(report["kind"], "tests");
    assert_eq!(report["testsTotal"], 2);
    assert_eq!(report["testsPassed"], 2);
}

#[test]
fn a_failing_test_names_itself_and_keeps_its_message() {
    if !python3_available() {
        return;
    }
    let report = run_fixture(BROKEN, SUITE);
    assert_eq!(report["testsTotal"], 2);
    assert_eq!(report["testsPassed"], 1);

    let failed = report["tests"]
        .as_array()
        .unwrap()
        .iter()
        .find(|t| t["status"] == "failed")
        .expect("one test should have failed");

    assert_eq!(failed["id"], "TestDouble.test_doubles_three");
    assert_eq!(failed["exception"], "AssertionError");
    assert!(
        failed["message"].as_str().unwrap().contains("adding is not doubling"),
        "the custom assertion message is the closest thing many tests have to \
         an authored condition, so it has to survive"
    );
}

#[test]
fn a_syntax_error_is_a_load_error_with_no_denominator() {
    if !python3_available() {
        return;
    }
    // The case both graders used to disagree on: the browser said 0 of 0 and
    // the desktop said 0 of 1.
    let report = run_fixture("def double(n)\n    return n * 2\n", SUITE);
    assert_eq!(report["kind"], "load_error");
    assert_eq!(report["testsTotal"], 0);
    assert_eq!(report["loadError"]["exception"], "SyntaxError");
}

#[test]
fn the_runner_leaves_nothing_behind_in_the_exercise_directory() {
    if !python3_available() {
        return;
    }
    let dir = tempfile::tempdir().unwrap();
    fs::write(dir.path().join("solution.py"), PASSING).unwrap();
    fs::write(dir.path().join("test.py"), SUITE).unwrap();

    let report = dir.path().join("report.json");
    Command::new("python3")
        .arg("-c")
        .arg(REPORT_RUNNER)
        .current_dir(dir.path())
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("ATLAS_EXERCISE_DIR", dir.path())
        .env("ATLAS_TEST_MODULE", "test")
        .env("ATLAS_REPORT_PATH", &report)
        .output()
        .unwrap();

    // The content build hashes every file in an exercise directory to decide
    // whether it moved underneath the learner's work, so a stray __pycache__
    // would show them "the exercise changed" after every run.
    let left: Vec<String> = fs::read_dir(dir.path())
        .unwrap()
        .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
        .filter(|name| name != "report.json")
        .collect();

    let mut sorted = left.clone();
    sorted.sort();
    assert_eq!(sorted, vec!["solution.py", "test.py"], "found {left:?}");
}
