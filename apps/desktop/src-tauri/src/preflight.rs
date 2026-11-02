//! Checking that the machine can run exercises, before a learner discovers it
//! cannot.
//!
//! Every check degrades rather than fails. A missing interpreter disables the
//! Run button and explains why; it never blocks reading a lesson, and it never
//! stops the app from starting.

use std::process::Command;

use serde::Serialize;
use tauri::AppHandle;

use crate::workspace;

/// The oldest Python the course supports. The exercises use `X | Y` unions in
/// annotations and `match`, both of which need 3.10.
const MIN_PYTHON: (u32, u32) = (3, 10);

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Check {
    pub name: String,
    pub ok: bool,
    /// What was found, when something was.
    pub detail: Option<String>,
    /// What to do about it. Present only when `ok` is false.
    pub remedy: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Preflight {
    /// False when something is wrong that stops exercises from running.
    pub can_run_exercises: bool,
    pub checks: Vec<Check>,
    pub workspace_path: Option<String>,
}

fn install_hint() -> &'static str {
    if cfg!(target_os = "macos") {
        "Install it with `brew install python@3.12`, or download it from python.org."
    } else if cfg!(target_os = "windows") {
        "Install it from python.org or the Microsoft Store, and make sure it is on PATH."
    } else {
        "Install it with your package manager, for example `sudo apt install python3`."
    }
}

/// Pull a (major, minor) out of `Python 3.12.4`.
fn parse_version(text: &str) -> Option<(u32, u32)> {
    let digits = text.split_whitespace().find(|part| {
        part.chars().next().is_some_and(|c| c.is_ascii_digit()) && part.contains('.')
    })?;

    let mut parts = digits.split('.');
    let major = parts.next()?.parse().ok()?;
    let minor = parts.next()?.parse().ok()?;
    Some((major, minor))
}

fn check_python() -> Check {
    let output = Command::new(crate::PYTHON).arg("--version").output();

    let Ok(output) = output else {
        return Check {
            name: crate::PYTHON.into(),
            ok: false,
            detail: None,
            remedy: Some(format!(
                "{} was not found on your PATH. {}",
                crate::PYTHON,
                install_hint()
            )),
        };
    };

    // Old versions of Python print the version to stderr.
    let mut text = String::from_utf8_lossy(&output.stdout).into_owned();
    text.push_str(&String::from_utf8_lossy(&output.stderr));
    let text = text.trim().to_string();

    match parse_version(&text) {
        Some(version) if version >= MIN_PYTHON => Check {
            name: crate::PYTHON.into(),
            ok: true,
            detail: Some(text),
            remedy: None,
        },
        Some((major, minor)) => Check {
            name: crate::PYTHON.into(),
            ok: false,
            detail: Some(text),
            remedy: Some(format!(
                "Found Python {major}.{minor}, but the exercises need {}.{} or newer. {}",
                MIN_PYTHON.0,
                MIN_PYTHON.1,
                install_hint()
            )),
        },
        None => Check {
            name: crate::PYTHON.into(),
            ok: false,
            detail: Some(text),
            remedy: Some(format!(
                "{} responded but its version could not be read. {}",
                crate::PYTHON,
                install_hint()
            )),
        },
    }
}

fn check_workspace(app: &AppHandle) -> (Check, Option<String>) {
    match workspace::ensure_root(app) {
        Ok(path) => {
            let shown = path.to_string_lossy().into_owned();
            (
                Check {
                    name: "workspace".into(),
                    ok: true,
                    detail: Some(shown.clone()),
                    remedy: None,
                },
                Some(shown),
            )
        }
        Err(error) => (
            Check {
                name: "workspace".into(),
                ok: false,
                detail: None,
                remedy: Some(format!(
                    "The exercise folder could not be created: {error:#}. \
                     Check that the app has permission to write to its data directory."
                )),
            },
            None,
        ),
    }
}

#[tauri::command]
pub fn preflight(app: AppHandle) -> Preflight {
    let python = check_python();
    let (workspace_check, workspace_path) = check_workspace(&app);

    Preflight {
        can_run_exercises: python.ok && workspace_check.ok,
        checks: vec![python, workspace_check],
        workspace_path,
    }
}

#[cfg(test)]
mod tests {
    use super::parse_version;

    #[test]
    fn reads_a_normal_version() {
        assert_eq!(parse_version("Python 3.12.4"), Some((3, 12)));
    }

    #[test]
    fn reads_a_two_part_version() {
        assert_eq!(parse_version("Python 3.10"), Some((3, 10)));
    }

    #[test]
    fn ignores_surrounding_noise() {
        assert_eq!(parse_version("  Python 3.11.9 \n"), Some((3, 11)));
    }

    #[test]
    fn rejects_nonsense() {
        assert_eq!(parse_version("command not found"), None);
        assert_eq!(parse_version(""), None);
    }
}
