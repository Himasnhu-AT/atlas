//! Rust backend for the Atlas Practice desktop shell.
//!
//! Two capabilities are exposed to the frontend, and nothing else:
//!
//! * an embedded terminal ([`pty`]) backed by real pseudo terminals, and
//! * a sandboxed workspace ([`workspace`]) rooted in the app-data directory.
//!
//! There is deliberately no general "run this command" IPC: `run_exercise`
//! composes a command from a fixed table and types it into a terminal the user
//! already has open, exactly as if they had typed it themselves.

mod analysis;
mod auth;
mod grader;
mod outbox;
mod preflight;
mod project;
mod pty;
mod sync;
mod workspace;

use anyhow::{bail, Context, Result};
use tauri::{AppHandle, Manager, State, WindowEvent};

/// Map a lesson language onto the interpreter that runs it.
fn interpreter_for(language: &str) -> Result<&'static str> {
    match language.trim().to_ascii_lowercase().as_str() {
        "python" | "python3" | "py" => Ok("python3"),
        "typescript" | "javascript" | "ts" | "js" | "node" => Ok("node"),
        "bash" | "sh" | "shell" => Ok("bash"),
        other => bail!("`{other}` is not a runnable exercise language"),
    }
}

fn build_run_line(app: &AppHandle, language: &str, rel_path: &str) -> Result<String> {
    let interpreter = interpreter_for(language)?;
    let root = workspace::ensure_root(app)?;
    let path = workspace::resolve(&root, rel_path)?;

    let meta = std::fs::metadata(&path)
        .with_context(|| format!("`{rel_path}` does not exist in the workspace"))?;
    if !meta.is_file() {
        bail!("`{rel_path}` is not a file");
    }

    let quoted = pty::shell_quote(&path.to_string_lossy());
    Ok(format!("{interpreter} {quoted}"))
}

/// Run an exercise file by typing the command into an existing terminal
/// session, so the learner sees (and keeps) the same shell they were using.
#[tauri::command]
fn run_exercise(
    app: AppHandle,
    manager: State<'_, pty::PtyManager>,
    pty_id: String,
    language: String,
    rel_path: String,
) -> Result<(), String> {
    let line = build_run_line(&app, &language, &rel_path).map_err(|e| format!("{e:#}"))?;
    pty::send_line(&manager, &pty_id, &line).map_err(|e| format!("{e:#}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        // Opens the pairing URL in the system browser. Scoped to https in
        // capabilities/default.json; it cannot execute anything.
        .plugin(tauri_plugin_shell::init())
        .manage(pty::PtyManager::default())
        .manage(project::ProjectState::default())
        .setup(|app| {
            workspace::ensure_root(app.handle())?;
            // A project root granted in a previous session is restored here, and
            // dropped if the directory has since moved or been deleted.
            project::restore(app.handle(), &app.state::<project::ProjectState>());
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(
                event,
                WindowEvent::Destroyed | WindowEvent::CloseRequested { .. }
            ) {
                window.app_handle().state::<pty::PtyManager>().kill_all();
            }
        })
        .invoke_handler(tauri::generate_handler![
            pty::pty_spawn,
            pty::pty_write,
            pty::pty_resize,
            pty::pty_kill,
            workspace::workspace_root,
            workspace::workspace_list,
            workspace::workspace_read,
            workspace::workspace_write,
            grader::run_tests,
            preflight::preflight,
            project::project_open,
            project::project_current,
            project::project_close,
            project::project_list,
            project::project_read,
            project::project_write,
            project::project_root,
            analysis::project_analyse,
            auth::auth_store,
            auth::auth_account,
            auth::auth_token,
            auth::auth_clear,
            sync::sync_queue,
            sync::sync_pending,
            sync::sync_drain,
            sync::sync_pair_start,
            sync::sync_pair_poll,
            run_exercise,
        ])
        .run(tauri::generate_context!())
        .expect("error while running the Atlas Practice desktop app");
}

#[cfg(test)]
mod tests {
    use super::interpreter_for;

    #[test]
    fn maps_known_languages() {
        assert_eq!(interpreter_for("python").unwrap(), "python3");
        assert_eq!(interpreter_for("TypeScript").unwrap(), "node");
        assert_eq!(interpreter_for(" bash ").unwrap(), "bash");
    }

    #[test]
    fn rejects_unknown_languages() {
        for bad in ["ruby", "", "python3 -c", "rm"] {
            assert!(
                interpreter_for(bad).is_err(),
                "expected `{bad}` to be rejected"
            );
        }
    }
}
