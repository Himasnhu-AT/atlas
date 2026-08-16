//! Working on the student's own repository.
//!
//! Exercises live in the app's sandbox, which the app creates and owns. A
//! project is different: it is the student's real code, in their real
//! repository, and the app becomes an editor for it.
//!
//! That means reaching outside the sandbox, so the rule is explicit consent.
//! A project root can only be established through the OS folder picker. There
//! is no command that takes a path from the frontend and opens it, because such
//! a command would let anything that can reach the IPC bridge read the disk.
//! The user points at a directory, and from then on every path is resolved
//! against that directory with the same containment guard the sandbox uses.
//!
//! Granted roots are remembered between sessions so the student does not
//! re-pick their repo every launch, and they are re-validated on load: a root
//! that has been deleted, moved, or replaced by a symlink is dropped.

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Runtime, State};
use tauri_plugin_dialog::DialogExt;

use crate::workspace::{self, FileEntry, SymlinkPolicy};

/// Directories never worth showing in a project tree, and never worth walking.
/// A `node_modules` with forty thousand entries is not navigation, it is a
/// denial of service against the renderer.
const IGNORED: &[&str] = &[
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    "dist",
    ".next",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
];

/// A single directory listing is capped so one pathological folder cannot
/// stall the window.
const MAX_ENTRIES: usize = 2_000;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Project {
    /// Absolute, canonicalized path to the granted root.
    pub path: String,
    /// The directory's own name, for display.
    pub name: String,
}

#[derive(Default)]
pub struct ProjectState {
    current: Mutex<Option<PathBuf>>,
}

impl ProjectState {
    fn set(&self, root: PathBuf) {
        *self.current.lock() = Some(root);
    }

    fn clear(&self) {
        *self.current.lock() = None;
    }

    /// The granted root, for the analyser, which lives in its own module.
    pub fn root_for_analysis(&self) -> Result<PathBuf> {
        self.root()
    }

    /// The granted root, or an error naming what the caller should do instead.
    fn root(&self) -> Result<PathBuf> {
        self.current
            .lock()
            .clone()
            .ok_or_else(|| anyhow::anyhow!("no project is open; choose a folder first"))
    }
}

fn remembered_path<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf> {
    Ok(app
        .path()
        .app_data_dir()
        .context("could not determine the application data directory")?
        .join("project.json"))
}

fn remember<R: Runtime>(app: &AppHandle<R>, root: &Path) -> Result<()> {
    let file = remembered_path(app)?;
    if let Some(parent) = file.parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::write(&file, root.to_string_lossy().as_bytes())
        .with_context(|| format!("could not record the project root at {}", file.display()))
}

fn forget<R: Runtime>(app: &AppHandle<R>) {
    if let Ok(file) = remembered_path(app) {
        let _ = fs::remove_file(file);
    }
}

/// Validate a candidate root before trusting it.
///
/// Canonicalizing here is what makes every later containment check meaningful:
/// the guard compares against this path, so it must already have every symlink
/// resolved out of it.
fn accept(candidate: &Path) -> Result<PathBuf> {
    let root = fs::canonicalize(candidate)
        .with_context(|| format!("{} could not be opened", candidate.display()))?;

    if !root.is_dir() {
        bail!("{} is not a directory", root.display());
    }

    // Opening `/` or a home directory turns a stray write into a very bad day,
    // and neither is ever a project.
    if root.parent().is_none() {
        bail!("the filesystem root cannot be opened as a project");
    }
    if let Some(home) = dirs_home() {
        if root == home {
            bail!("choose a project folder rather than your whole home directory");
        }
    }

    Ok(root)
}

fn dirs_home() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

fn describe(root: &Path) -> Project {
    Project {
        path: root.to_string_lossy().into_owned(),
        name: root
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| root.to_string_lossy().into_owned()),
    }
}

/// Restore a previously granted root at startup, if it is still valid.
pub fn restore<R: Runtime>(app: &AppHandle<R>, state: &ProjectState) {
    let Ok(file) = remembered_path(app) else { return };
    let Ok(raw) = fs::read_to_string(&file) else { return };
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return;
    }

    match accept(Path::new(trimmed)) {
        Ok(root) => state.set(root),
        // The repo moved or was deleted. Drop it rather than carrying a stale
        // grant that would fail on every call.
        Err(_) => forget(app),
    }
}

// --- commands ---------------------------------------------------------------

/// Ask the user for a folder and adopt it as the project root.
///
/// The path comes from the OS dialog and nowhere else. Returns `None` when the
/// user cancels, which is not an error.
#[tauri::command]
pub async fn project_open(
    app: AppHandle,
    state: State<'_, ProjectState>,
) -> Result<Option<Project>, String> {
    let picked = app.dialog().file().blocking_pick_folder();

    let Some(picked) = picked else { return Ok(None) };

    let candidate = picked
        .into_path()
        .map_err(|e| format!("that folder could not be read: {e}"))?;

    let root = accept(&candidate).map_err(|e| format!("{e:#}"))?;
    remember(&app, &root).map_err(|e| format!("{e:#}"))?;
    state.set(root.clone());

    Ok(Some(describe(&root)))
}

#[tauri::command]
pub fn project_current(state: State<'_, ProjectState>) -> Option<Project> {
    state.current.lock().as_deref().map(describe)
}

#[tauri::command]
pub fn project_close(app: AppHandle, state: State<'_, ProjectState>) {
    state.clear();
    forget(&app);
}

#[tauri::command]
pub fn project_list(state: State<'_, ProjectState>, rel: String) -> Result<Vec<FileEntry>, String> {
    let root = state.root().map_err(|e| format!("{e:#}"))?;
    list_filtered(&root, &rel).map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn project_read(state: State<'_, ProjectState>, rel: String) -> Result<String, String> {
    let root = state.root().map_err(|e| format!("{e:#}"))?;
    let path = workspace::resolve_within(&root, &rel, SymlinkPolicy::AllowInternal)
        .map_err(|e| format!("{e:#}"))?;

    let meta = fs::metadata(&path).map_err(|_| format!("`{rel}` does not exist"))?;
    if !meta.is_file() {
        return Err(format!("`{rel}` is not a file"));
    }
    // Reading a 200MB binary into the webview helps nobody.
    if meta.len() > 2 * 1024 * 1024 {
        return Err(format!("`{rel}` is too large to open here"));
    }

    fs::read_to_string(&path).map_err(|_| format!("`{rel}` is not UTF-8 text"))
}

#[tauri::command]
pub fn project_write(
    state: State<'_, ProjectState>,
    rel: String,
    contents: String,
) -> Result<(), String> {
    let root = state.root().map_err(|e| format!("{e:#}"))?;
    let path = workspace::resolve_within(&root, &rel, SymlinkPolicy::AllowInternal)
        .map_err(|e| format!("{e:#}"))?;

    if contents.len() > 5 * 1024 * 1024 {
        return Err("that file is too large to save".into());
    }

    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("could not create {}: {e}", parent.display()))?;
    }

    fs::write(&path, contents).map_err(|e| format!("could not write `{rel}`: {e}"))
}

/// The absolute path of the granted root, for the terminal's working directory.
#[tauri::command]
pub fn project_root(state: State<'_, ProjectState>) -> Result<String, String> {
    state
        .root()
        .map(|root| root.to_string_lossy().into_owned())
        .map_err(|e| format!("{e:#}"))
}

fn list_filtered(root: &Path, rel: &str) -> Result<Vec<FileEntry>> {
    let dir = workspace::resolve_within(root, rel, SymlinkPolicy::AllowInternal)?;

    let meta = fs::metadata(&dir).with_context(|| format!("`{rel}` does not exist"))?;
    if !meta.is_dir() {
        bail!("`{rel}` is not a directory");
    }

    let mut entries = Vec::new();
    for entry in fs::read_dir(&dir).with_context(|| format!("could not read `{rel}`"))? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().into_owned();

        if IGNORED.contains(&name.as_str()) {
            continue;
        }

        let is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false);
        let child_rel = if rel.is_empty() {
            name.clone()
        } else {
            format!("{}/{}", rel.trim_end_matches('/'), name)
        };

        entries.push(FileEntry::new(name, child_rel, is_dir));

        if entries.len() >= MAX_ENTRIES {
            break;
        }
    }

    // Directories first, then alphabetical, which is what every file tree does
    // and therefore what a reader expects without being told.
    entries.sort_by(|a, b| b.is_dir.cmp(&a.is_dir).then_with(|| a.name.cmp(&b.name)));
    Ok(entries)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn temp() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("learn-project-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        fs::canonicalize(&dir).unwrap()
    }

    #[test]
    fn accepts_an_ordinary_directory() {
        let dir = temp();
        assert!(accept(&dir).is_ok());
    }

    #[test]
    fn rejects_a_file() {
        let dir = temp();
        let file = dir.join("a.txt");
        fs::write(&file, "x").unwrap();
        assert!(accept(&file).is_err());
    }

    #[test]
    fn rejects_the_filesystem_root() {
        assert!(accept(Path::new("/")).is_err());
    }

    #[test]
    fn listing_hides_noise_directories() {
        let dir = temp();
        fs::create_dir_all(dir.join("node_modules")).unwrap();
        fs::create_dir_all(dir.join("src")).unwrap();
        fs::write(dir.join("main.py"), "x").unwrap();

        let names: Vec<_> = list_filtered(&dir, "").unwrap().into_iter().map(|e| e.name).collect();
        assert!(names.contains(&"src".to_string()));
        assert!(names.contains(&"main.py".to_string()));
        assert!(!names.contains(&"node_modules".to_string()));
    }

    #[test]
    fn listing_puts_directories_first() {
        let dir = temp();
        fs::write(dir.join("a-file.py"), "x").unwrap();
        fs::create_dir_all(dir.join("z-dir")).unwrap();

        let entries = list_filtered(&dir, "").unwrap();
        assert!(entries[0].is_dir, "directories should sort ahead of files");
    }

    #[test]
    fn a_symlink_inside_the_root_is_allowed() {
        let dir = temp();
        fs::create_dir_all(dir.join("real")).unwrap();
        fs::write(dir.join("real/mod.py"), "x").unwrap();
        std::os::unix::fs::symlink(dir.join("real"), dir.join("link")).unwrap();

        assert!(
            workspace::resolve_within(&dir, "link/mod.py", SymlinkPolicy::AllowInternal).is_ok(),
            "a repo's internal symlink must not break the editor"
        );
    }

    #[test]
    fn a_symlink_escaping_the_root_is_refused() {
        let dir = temp();
        std::os::unix::fs::symlink("/etc", dir.join("escape")).unwrap();

        assert!(
            workspace::resolve_within(&dir, "escape/hosts", SymlinkPolicy::AllowInternal).is_err(),
            "a symlink pointing outside the granted directory must be refused"
        );
    }

    #[test]
    fn parent_traversal_is_still_refused() {
        let dir = temp();
        assert!(
            workspace::resolve_within(&dir, "../secrets", SymlinkPolicy::AllowInternal).is_err()
        );
    }
}
