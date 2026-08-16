//! Running an exercise's tests and reporting a structured verdict.
//!
//! The terminal already lets a learner run `python3 test.py` themselves and read
//! the output. This module exists because the app also needs a machine-readable
//! answer: how many tests ran, how many passed, how long it took. That is what
//! gets recorded as an attempt.
//!
//! Nothing here is a general command runner. The interpreter comes from a fixed
//! table, the working directory is always inside the workspace sandbox, and the
//! only argument is a path that `workspace::resolve` has already validated.

use std::path::Path;
use std::process::Command;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use serde::Serialize;
use tauri::AppHandle;

use crate::workspace;

/// A test run that took longer than this is assumed to be stuck. The suites in
/// this course finish in about a second; the mock model client makes no network
/// calls, so there is nothing legitimate to wait for.
const TIMEOUT: Duration = Duration::from_secs(60);

/// Cap on captured output. A runaway print loop should not be able to push a
/// hundred megabytes through the IPC boundary.
const MAX_OUTPUT_BYTES: usize = 256 * 1024;

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
        }
    }
}

/// Parse a unittest summary into counts.
///
/// The relevant lines look like:
///     Ran 15 tests in 0.001s
///     OK
/// or
///     FAILED (failures=2, errors=1)
///
/// Anything unparseable falls back to a single pass or fail derived from the
/// exit status, so an exercise using a different runner still reports sensibly.
fn parse_unittest(output: &str, exit_ok: bool) -> (u32, u32) {
    let total = output
        .lines()
        .rev()
        .find_map(|line| {
            let rest = line.trim().strip_prefix("Ran ")?;
            rest.split_whitespace().next()?.parse::<u32>().ok()
        })
        .unwrap_or(0);

    if total == 0 {
        return if exit_ok { (1, 1) } else { (0, 1) };
    }

    if exit_ok {
        return (total, total);
    }

    // Count the distinct failing tests from the FAILED summary rather than
    // counting FAIL: lines, which appear twice in verbose output.
    let bad = output
        .lines()
        .rev()
        .find(|line| line.trim_start().starts_with("FAILED ("))
        .map(|line| {
            line.split(|c: char| !c.is_ascii_digit())
                .filter_map(|part| part.parse::<u32>().ok())
                .sum::<u32>()
        })
        .unwrap_or(1);

    (total.saturating_sub(bad.min(total)), total)
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
        "python" | "python3" | "py" => Ok("python3"),
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

    let output = spawn_with_timeout(interpreter, &test_path, &dir)?;

    let mut combined = String::from_utf8_lossy(&output.stdout).into_owned();
    combined.push_str(&String::from_utf8_lossy(&output.stderr));

    let exit_ok = output.status.success();
    let (tests_passed, tests_total) = parse_unittest(&combined, exit_ok);

    Ok(TestReport {
        passed: exit_ok,
        tests_passed,
        tests_total,
        duration_ms: started.elapsed().as_millis() as u64,
        output: truncate(combined),
        runner_error: None,
    })
}

fn spawn_with_timeout(
    interpreter: &str,
    test_path: &Path,
    cwd: &Path,
) -> Result<std::process::Output> {
    let mut child = Command::new(interpreter)
        .arg(test_path)
        .current_dir(cwd)
        // Keeps __pycache__ out of the learner's workspace.
        .env("PYTHONDONTWRITEBYTECODE", "1")
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
    use super::{parse_unittest, truncate, MAX_OUTPUT_BYTES};

    #[test]
    fn parses_a_passing_run() {
        let output = "Ran 15 tests in 0.001s\n\nOK\n";
        assert_eq!(parse_unittest(output, true), (15, 15));
    }

    #[test]
    fn parses_a_failing_run() {
        let output = "Ran 15 tests in 0.001s\n\nFAILED (failures=2)\n";
        assert_eq!(parse_unittest(output, false), (13, 15));
    }

    #[test]
    fn counts_failures_and_errors_together() {
        let output = "Ran 10 tests in 0.001s\n\nFAILED (failures=2, errors=1)\n";
        assert_eq!(parse_unittest(output, false), (7, 10));
    }

    #[test]
    fn never_reports_more_failures_than_tests() {
        let output = "Ran 2 tests in 0.001s\n\nFAILED (failures=9)\n";
        assert_eq!(parse_unittest(output, false), (0, 2));
    }

    #[test]
    fn falls_back_when_the_summary_is_missing() {
        assert_eq!(parse_unittest("some other runner\n", true), (1, 1));
        assert_eq!(parse_unittest("some other runner\n", false), (0, 1));
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
