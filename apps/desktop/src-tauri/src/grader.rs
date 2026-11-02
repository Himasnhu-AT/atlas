//! Running an exercise's tests and reporting a structured verdict.
//!
//! The terminal already lets a learner run `python3 test.py` themselves and read
//! the output. This module exists because the app also needs a machine-readable
//! answer: how many tests ran, how many passed, how long it took. That is what
//! gets recorded as an attempt.
//!
//! Nothing here is a general command runner. The interpreter comes from a fixed
//! table, the working directory is always inside the workspace sandbox, and the
//! only argument is a program text that is a compile-time constant in this
//! binary. Nothing a caller supplies is ever formatted into it: the exercise
//! directory and the test module name are passed in the environment.
//!
//! The counts used to come from string-scraping unittest's summary, which
//! could not tell a syntax error from every test failing and answered `(0, 1)`
//! whenever it could not parse. They now come from
//! `packages/learning/runner/atlas_report.py`, the same file the browser
//! grader fetches, which reads the unittest result object directly. That is
//! what makes "exercises grade in two places and must mean the same thing in
//! both" a fact about one file rather than a promise about two.

use std::path::Path;
use std::process::Command;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use tauri::AppHandle;

use crate::workspace;

/// A test run that took longer than this is assumed to be stuck. The suites in
/// this course finish in about a second; the mock model client makes no network
/// calls, so there is nothing legitimate to wait for.
const TIMEOUT: Duration = Duration::from_secs(60);

/// Cap on captured output. A runaway print loop should not be able to push a
/// hundred megabytes through the IPC boundary.
const MAX_OUTPUT_BYTES: usize = 256 * 1024;

/// The shared report runner, compiled in.
///
/// `include_str!` rather than a copy on disk, because the invariant that both
/// graders mean the same thing only holds if there is one file to change.
const REPORT_RUNNER: &str = include_str!("../../../../packages/learning/runner/atlas_report.py");

/// What happened to one test. Mirrors `TestOutcome` in
/// `packages/core/src/grading.ts` and is deserialised verbatim from the JSON
/// the runner writes, which is why the field names are camelCase on both sides.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TestOutcome {
    /// `ClassName.test_method`. The key an exercise's case map is written on.
    pub id: String,
    pub status: TestStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exception: Option<String>,
    /// The assertion message, not the traceback. The traceback is `output`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    /// Deepest frame in a file the learner owns.
    #[serde(rename = "where", skip_serializing_if = "Option::is_none")]
    pub location: Option<Frame>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TestStatus {
    Passed,
    Failed,
    Error,
    Skipped,
    /// Loaded, but never reached, because `setUpClass` raised.
    NotRun,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Frame {
    pub file: String,
    pub line: u32,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RunKind {
    /// The suite loaded and ran. The only kind with a meaningful denominator.
    Tests,
    /// The suite would not import. A syntax error, usually. Nothing ran.
    LoadError,
    /// The process died without writing a report.
    Crashed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LoadError {
    pub exception: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RunOutcome {
    pub kind: RunKind,
    pub tests_total: u32,
    pub tests_passed: u32,
    pub tests: Vec<TestOutcome>,
    pub truncated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub load_error: Option<LoadError>,
}

impl RunOutcome {
    /// A run that produced no report at all: `os._exit`, a segfault, a kill.
    ///
    /// The old text scraper answered this with `(0, 1)`, inventing a test that
    /// never existed. Saying nothing ran is both true and more useful.
    fn crashed() -> Self {
        Self {
            kind: RunKind::Crashed,
            tests_total: 0,
            tests_passed: 0,
            tests: Vec::new(),
            truncated: false,
            load_error: None,
        }
    }

    /// A language with no structured runner. Only Python has one, and every
    /// exercise in the catalogue is Python; this keeps `bash` reporting
    /// something honest rather than nothing.
    fn from_exit_status(ok: bool) -> Self {
        Self {
            kind: RunKind::Tests,
            tests_total: 1,
            tests_passed: if ok { 1 } else { 0 },
            tests: Vec::new(),
            truncated: false,
            load_error: None,
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TestReport {
    pub passed: bool,
    pub tests_passed: u32,
    pub tests_total: u32,
    pub duration_ms: u64,
    /// Combined stdout and stderr, truncated. unittest writes its summary to
    /// stderr, so both are needed and interleaving them is what the learner
    /// would have seen in a terminal anyway.
    pub output: String,
    /// Set when the runner itself failed, as opposed to tests failing. A missing
    /// interpreter is not a red test.
    pub runner_error: Option<String>,
    /// The structured half: which tests, and what each one said.
    ///
    /// `tests_passed` and `tests_total` above are copied out of this, so
    /// nothing can report one number in the status bar and a different one in
    /// the results panel.
    pub outcome: RunOutcome,
}

impl TestReport {
    fn runner_error(message: impl Into<String>, duration: Duration) -> Self {
        Self {
            passed: false,
            tests_passed: 0,
            tests_total: 0,
            duration_ms: duration.as_millis() as u64,
            output: String::new(),
            runner_error: Some(message.into()),
            outcome: RunOutcome::crashed(),
        }
    }
}

fn truncate(mut text: String) -> String {
    if text.len() <= MAX_OUTPUT_BYTES {
        return text;
    }
    // Keep the tail: the summary a learner needs is at the end.
    let cut = text.len() - MAX_OUTPUT_BYTES;
    let boundary = (cut..text.len())
        .find(|i| text.is_char_boundary(*i))
        .unwrap_or(text.len());
    text = text.split_off(boundary);
    format!("[output truncated]\n{text}")
}

fn interpreter_for(language: &str) -> Result<&'static str> {
    match language.trim().to_ascii_lowercase().as_str() {
        "python" | "python3" | "py" => Ok(crate::PYTHON),
        "bash" | "sh" | "shell" => Ok("bash"),
        other => bail!("`{other}` is not a runnable exercise language"),
    }
}

/// Run the tests for one exercise directory.
///
/// `rel_dir` is the exercise's directory inside the workspace; `test_file` is
/// the name of the test within it. Both go through `workspace::resolve`, so
/// neither can escape the sandbox.
pub fn run(app: &AppHandle, rel_dir: &str, test_file: &str, language: &str) -> TestReport {
    let started = Instant::now();

    match run_inner(app, rel_dir, test_file, language, started) {
        Ok(report) => report,
        Err(error) => TestReport::runner_error(format!("{error:#}"), started.elapsed()),
    }
}

fn run_inner(
    app: &AppHandle,
    rel_dir: &str,
    test_file: &str,
    language: &str,
    started: Instant,
) -> Result<TestReport> {
    let interpreter = interpreter_for(language)?;
    let root = workspace::ensure_root(app)?;
    let dir = workspace::resolve(&root, rel_dir)?;

    if !dir.is_dir() {
        bail!("`{rel_dir}` is not a directory in the workspace");
    }

    // Reject a test filename containing a separator rather than joining it
    // blindly. Resolving it through the workspace guard keeps the check in one
    // place.
    if test_file.contains('/') || test_file.contains('\\') || test_file.contains("..") {
        bail!("`{test_file}` is not a plain filename");
    }
    let test_path = dir.join(test_file);
    if !test_path.is_file() {
        bail!("`{test_file}` does not exist in `{rel_dir}`");
    }

    // The report goes to a file this process names, in the OS temp directory
    // rather than the sandbox. `workspace::resolve` guards paths a caller
    // supplies, and no caller supplies this one; `NamedTempFile` creates with
    // O_EXCL, so a symlink planted in the temp directory cannot be the target.
    // Writing it into the exercise directory instead would be worse: the
    // content build hashes every file in there to decide whether the exercise
    // moved underneath the learner's work.
    let report_file = tempfile::NamedTempFile::new().context("creating the report file")?;

    // `test_file` has already been checked for separators and proven to exist.
    // Python wants it as a module name.
    let module = test_file.strip_suffix(".py").unwrap_or(test_file);

    let output = spawn_with_timeout(interpreter, &dir, module, report_file.path())?;

    let mut combined = String::from_utf8_lossy(&output.stdout).into_owned();
    combined.push_str(&String::from_utf8_lossy(&output.stderr));

    let exit_ok = output.status.success();
    let outcome = if interpreter == crate::PYTHON {
        read_report(report_file.path())
    } else {
        RunOutcome::from_exit_status(exit_ok)
    };

    Ok(TestReport {
        passed: outcome.kind == RunKind::Tests
            && outcome.tests_total > 0
            && outcome.tests_passed == outcome.tests_total,
        tests_passed: outcome.tests_passed,
        tests_total: outcome.tests_total,
        duration_ms: started.elapsed().as_millis() as u64,
        output: truncate(combined),
        runner_error: None,
        outcome,
    })
}

/// Read the report the runner wrote, or conclude that it never got that far.
fn read_report(path: &Path) -> RunOutcome {
    match std::fs::read_to_string(path) {
        Ok(raw) => serde_json::from_str(&raw).unwrap_or_else(|_| RunOutcome::crashed()),
        Err(_) => RunOutcome::crashed(),
    }
}

fn spawn_with_timeout(
    interpreter: &str,
    cwd: &Path,
    test_module: &str,
    report_path: &Path,
) -> Result<std::process::Output> {
    let mut child = Command::new(interpreter)
        // The program text is a constant in this binary. A caller chooses the
        // directory and the module name, and both travel in the environment,
        // so nothing a caller supplies is ever formatted into the source the
        // interpreter is handed.
        .arg("-c")
        .arg(REPORT_RUNNER)
        .current_dir(cwd)
        // Keeps __pycache__ out of the learner's workspace.
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("ATLAS_EXERCISE_DIR", cwd)
        .env("ATLAS_TEST_MODULE", test_module)
        .env("ATLAS_REPORT_PATH", report_path)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .with_context(|| format!("could not start `{interpreter}`"))?;

    let deadline = Instant::now() + TIMEOUT;
    loop {
        if let Some(_status) = child.try_wait()? {
            return child.wait_with_output().context("reading test output");
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            bail!(
                "the tests did not finish within {} seconds and were stopped",
                TIMEOUT.as_secs()
            );
        }
        std::thread::sleep(Duration::from_millis(25));
    }
}

#[tauri::command]
pub fn run_tests(
    app: AppHandle,
    rel_dir: String,
    test_file: String,
    language: String,
) -> TestReport {
    run(&app, &rel_dir, &test_file, &language)
}

#[cfg(test)]
mod tests {
    use super::{read_report, truncate, RunKind, TestStatus, MAX_OUTPUT_BYTES, REPORT_RUNNER};
    use std::io::Write;

    /// A report the shared runner could have written.
    const REPORT: &str = r#"{
        "kind": "tests",
        "testsTotal": 3,
        "testsPassed": 2,
        "truncated": false,
        "tests": [
            {"id": "TestX.test_a", "status": "passed", "durationMs": 1},
            {"id": "TestX.test_b", "status": "failed", "exception": "AssertionError",
             "message": "5 != 6 : adding is not doubling",
             "where": {"file": "test.py", "line": 9}}
        ]
    }"#;

    fn written(body: &str) -> tempfile::NamedTempFile {
        let mut file = tempfile::NamedTempFile::new().unwrap();
        file.write_all(body.as_bytes()).unwrap();
        file.flush().unwrap();
        file
    }

    #[test]
    fn parses_a_report_written_by_the_runner() {
        let file = written(REPORT);
        let outcome = read_report(file.path());

        assert_eq!(outcome.kind, RunKind::Tests);
        assert_eq!(outcome.tests_total, 3);
        assert_eq!(outcome.tests_passed, 2);

        let failed = &outcome.tests[1];
        assert_eq!(failed.id, "TestX.test_b");
        assert_eq!(failed.status, TestStatus::Failed);
        assert_eq!(failed.exception.as_deref(), Some("AssertionError"));
        assert!(failed.message.as_deref().unwrap().contains("adding is not doubling"));
        assert_eq!(failed.location.as_ref().unwrap().line, 9);
    }

    #[test]
    fn a_syntax_error_is_a_load_error_not_a_suite_of_failures() {
        let file = written(
            r#"{"kind": "load_error", "testsTotal": 0, "testsPassed": 0,
                "truncated": false, "tests": [],
                "loadError": {"exception": "SyntaxError", "message": "expected ':'",
                              "file": "solution.py", "line": 12}}"#,
        );
        let outcome = read_report(file.path());

        assert_eq!(outcome.kind, RunKind::LoadError);
        assert_eq!(outcome.tests_total, 0);
        let error = outcome.load_error.unwrap();
        assert_eq!(error.exception, "SyntaxError");
        assert_eq!(error.line, Some(12));
    }

    #[test]
    fn tests_that_never_ran_are_not_reported_as_passing() {
        let file = written(
            r#"{"kind": "tests", "testsTotal": 2, "testsPassed": 0, "truncated": false,
                "tests": [{"id": "T.test_a", "status": "not_run"},
                          {"id": "T.test_b", "status": "not_run"}]}"#,
        );
        let outcome = read_report(file.path());
        assert_eq!(outcome.tests_passed, 0);
        assert!(outcome.tests.iter().all(|t| t.status == TestStatus::NotRun));
    }

    #[test]
    fn a_missing_report_is_a_crash_not_a_failing_test() {
        // The old text scraper answered this case with `(0, 1)`, inventing a
        // test that never existed.
        let outcome = read_report(std::path::Path::new("/nonexistent/atlas/report.json"));
        assert_eq!(outcome.kind, RunKind::Crashed);
        assert_eq!(outcome.tests_total, 0);
        assert_eq!(outcome.tests_passed, 0);
    }

    #[test]
    fn an_unparseable_report_is_a_crash() {
        let file = written("not json at all");
        assert_eq!(read_report(file.path()).kind, RunKind::Crashed);
    }

    #[test]
    fn the_compiled_in_runner_is_the_shared_one() {
        // `include_str!` is resolved at compile time, so a moved or renamed
        // runner is a build failure rather than a silent divergence. This only
        // guards against including the wrong file.
        assert!(REPORT_RUNNER.contains("def run(directory"));
        assert!(REPORT_RUNNER.contains("def load_ids(directory"));
        assert!(REPORT_RUNNER.contains("ATLAS_REPORT_PATH"));
    }

    #[test]
    fn truncate_keeps_the_tail_and_a_char_boundary() {
        let text = "é".repeat(MAX_OUTPUT_BYTES);
        let out = truncate(text);
        assert!(out.starts_with("[output truncated]"));
        assert!(out.len() <= MAX_OUTPUT_BYTES + 32);
    }

    #[test]
    fn truncate_leaves_short_output_alone() {
        assert_eq!(truncate("short".into()), "short");
    }
}
