//! Static analysis of the student's Python, with no model involved.
//!
//! A project is the student's own code, so there is no reference solution to
//! diff against and no scripted test suite that knows the right answer. What we
//! can still do, entirely offline and in well under a second, is tell them
//! whether the code parses, whether it imports things it never defines, whether
//! a function they call exists, and whether they left a stub unfinished.
//!
//! That is the honest boundary of static checking, and it catches the majority
//! of what stops an agent from running at all. Whether the agent is any *good*
//! is a question only a live model can answer, which is the separate, explicit,
//! opt-in step.
//!
//! Standard library only, because the student's repo is not ours to install
//! into.

use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::project::ProjectState;
use crate::workspace::{resolve_within, SymlinkPolicy};

const TIMEOUT: Duration = Duration::from_secs(30);

/// The analyser, shipped as a string and fed to `python3 -` on stdin.
///
/// Written to a temp file would leave litter in the student's repo; passed on
/// stdin it leaves nothing behind and cannot collide with their own filenames.
const ANALYSER: &str = include_str!("../python/analyse.py");

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Diagnostic {
    /// Path relative to the project root.
    pub file: String,
    pub line: u32,
    pub column: u32,
    /// `error` stops the code running at all; `warning` is worth fixing.
    pub severity: String,
    pub message: String,
    /// Short machine-readable kind, e.g. `syntax`, `undefined-name`, `stub`.
    pub rule: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AnalysisReport {
    pub ok: bool,
    pub files_checked: u32,
    pub diagnostics: Vec<Diagnostic>,
    pub duration_ms: u64,
    /// Set when the analyser itself could not run, as distinct from finding
    /// problems. A missing interpreter is not a code defect.
    pub runner_error: Option<String>,
}

#[derive(Deserialize)]
struct RawReport {
    files_checked: u32,
    diagnostics: Vec<Diagnostic>,
}

fn analyse(root: &Path, rel: &str) -> Result<AnalysisReport> {
    let started = Instant::now();

    let target = resolve_within(root, rel, SymlinkPolicy::AllowInternal)?;
    if !target.exists() {
        bail!("`{rel}` does not exist in this project");
    }

    let mut child = Command::new(crate::PYTHON)
        .arg("-")
        .arg(&target)
        .current_dir(root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("could not start python3")?;

    {
        use std::io::Write;
        let stdin = child.stdin.as_mut().context("could not write to python3")?;
        stdin.write_all(ANALYSER.as_bytes())?;
    }

    let deadline = Instant::now() + TIMEOUT;
    loop {
        if child.try_wait()?.is_some() {
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            bail!("analysis did not finish within {} seconds", TIMEOUT.as_secs());
        }
        std::thread::sleep(Duration::from_millis(20));
    }

    let output = child.wait_with_output().context("reading analysis output")?;
    let stdout = String::from_utf8_lossy(&output.stdout);

    let raw: RawReport = serde_json::from_str(stdout.trim()).with_context(|| {
        let stderr = String::from_utf8_lossy(&output.stderr);
        format!("the analyser produced unreadable output: {}", stderr.trim())
    })?;

    let has_error = raw.diagnostics.iter().any(|d| d.severity == "error");

    Ok(AnalysisReport {
        ok: !has_error,
        files_checked: raw.files_checked,
        diagnostics: raw.diagnostics,
        duration_ms: started.elapsed().as_millis() as u64,
        runner_error: None,
    })
}

/// Statically check a file or directory in the open project.
///
/// Never rejects for finding problems: diagnostics are a successful result.
/// `runnerError` is set only when the analysis itself could not happen.
#[tauri::command]
pub fn project_analyse(state: State<'_, ProjectState>, rel: String) -> AnalysisReport {
    let started = Instant::now();

    let report = state
        .root_for_analysis()
        .and_then(|root| analyse(&root, &rel));

    match report {
        Ok(report) => report,
        Err(error) => AnalysisReport {
            ok: false,
            files_checked: 0,
            diagnostics: Vec::new(),
            duration_ms: started.elapsed().as_millis() as u64,
            runner_error: Some(format!("{error:#}")),
        },
    }
}
