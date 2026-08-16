//! Sandboxed workspace filesystem.
//!
//! Everything the learner writes lives under a single directory inside the
//! app-data dir. Every path that crosses the IPC boundary is a *relative* path
//! and is validated by [`resolve`] before it is used, so a compromised frontend
//! cannot read or write outside the sandbox.

use std::fs;
use std::path::{Component, Path, PathBuf};

use anyhow::{anyhow, bail, Context, Result};
use serde::Serialize;
use tauri::{AppHandle, Manager, Runtime};

/// Hard ceiling on a single `workspace_write` payload (5 MiB).
pub const MAX_WRITE_BYTES: usize = 5 * 1024 * 1024;
/// Hard ceiling on a single `workspace_read` result (5 MiB).
pub const MAX_READ_BYTES: u64 = 5 * 1024 * 1024;

const SEED_README: &str = "\
# Your practice workspace

Everything in this folder is yours. The embedded terminal opens here, and the
`Run` button executes the file you are editing from this directory.

  exercises/   scratch space for the code you write while working through lessons

Nothing outside this folder is reachable from the app: `..`, absolute paths and
symlinks are all rejected at the IPC boundary.
";

#[derive(Debug, Clone)]
pub struct FileEntry {
    /// File or directory name (no separators).
    pub name: String,
    /// Path relative to the workspace root, using `/` separators. This is the
    /// exact value to hand back to `workspace_list` / `read` / `write`.
    pub path: String,
    pub is_dir: bool,
}

impl FileEntry {
    pub fn new(name: String, path: String, is_dir: bool) -> Self {
        Self { name, path, is_dir }
    }
}

/// Serialized by hand so the directory flag ships under *both* the snake_case
/// name from the Rust struct and the camelCase name a TypeScript caller would
/// reach for. The frontend is written against the IPC contract independently of
/// this file, and a silent `undefined` there would render every entry as a file.
impl Serialize for FileEntry {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        use serde::ser::SerializeStruct;
        let mut entry = serializer.serialize_struct("FileEntry", 4)?;
        entry.serialize_field("name", &self.name)?;
        entry.serialize_field("path", &self.path)?;
        entry.serialize_field("is_dir", &self.is_dir)?;
        entry.serialize_field("isDir", &self.is_dir)?;
        entry.end()
    }
}

/// Return the workspace root, creating and seeding it on first use.
///
/// The returned path is canonicalized, which is what makes the containment
/// checks in [`resolve`] meaningful.
pub fn ensure_root<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf> {
    let data_dir = app
        .path()
        .app_data_dir()
        .context("could not determine the application data directory")?;
    let root = data_dir.join("workspace");

    if !root.exists() {
        fs::create_dir_all(&root)
            .with_context(|| format!("could not create workspace at {}", root.display()))?;
    }

    let root = fs::canonicalize(&root)
        .with_context(|| format!("could not canonicalize workspace at {}", root.display()))?;

    let readme = root.join("README.md");
    if !readme.exists() {
        fs::write(&readme, SEED_README).context("could not seed the workspace README")?;
    }
    let exercises = root.join("exercises");
    if !exercises.exists() {
        fs::create_dir_all(&exercises).context("could not seed the exercises directory")?;
    }

    Ok(root)
}

/// Turn a caller-supplied relative path into an absolute path that is proven to
/// live inside `root`.
///
/// Three independent defenses, all of which must pass:
///
/// 1. **Lexical** — the path is walked component by component. `..`, a leading
///    `/`, and Windows drive prefixes are rejected outright rather than
///    normalized away, so `a/../../etc` never becomes `../etc`.
/// 2. **Symlink** — every existing ancestor of the target is checked with
///    `symlink_metadata`; a symlink anywhere along the chain is refused. This
///    is what stops `ln -s / esc` inside the workspace from becoming an escape.
/// 3. **Canonical** — the deepest ancestor that actually exists is
///    canonicalized and must still be prefixed by `root`. This catches anything
///    the first two passes missed (e.g. a root that is itself relocated).
pub fn resolve(root: &Path, rel: &str) -> Result<PathBuf> {
    resolve_within(root, rel, SymlinkPolicy::Forbid)
}

/// Whether a symlink is tolerated between the root and the target.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum SymlinkPolicy {
    /// The app's own sandbox. Nothing in it is created by a human, so any
    /// symlink is either a bug or an attack, and both deserve refusal.
    Forbid,
    /// A directory the user explicitly granted through the OS picker. Real
    /// repositories contain symlinks as a matter of course (`node_modules/.bin`,
    /// vendored packages, a `latest` pointer), and refusing all of them would
    /// make the IDE useless on ordinary projects.
    ///
    /// This is not a weaker guarantee about escape. Pass 3 still canonicalizes
    /// and still requires containment, so a symlink pointing anywhere outside
    /// the granted root is rejected exactly as before. What changes is only
    /// that a symlink resolving to somewhere *inside* the root is allowed.
    AllowInternal,
}

pub fn resolve_within(root: &Path, rel: &str, policy: SymlinkPolicy) -> Result<PathBuf> {
    if rel.contains('\0') {
        bail!("path contains a NUL byte");
    }

    // Pass 1: lexical.
    let requested = Path::new(rel);
    let mut resolved = root.to_path_buf();
    for component in requested.components() {
        match component {
            Component::Normal(part) => {
                let part = part
                    .to_str()
                    .ok_or_else(|| anyhow!("path component is not valid UTF-8"))?;
                resolved.push(part);
            }
            Component::CurDir => {}
            Component::ParentDir => bail!("`..` is not allowed in workspace paths"),
            Component::RootDir | Component::Prefix(_) => {
                bail!("absolute paths are not allowed in the workspace")
            }
        }
    }

    // Pass 2: no symlinks anywhere between the root and the target, unless the
    // caller granted this directory and asked to tolerate internal ones.
    //
    // Pass 1 only ever pushes onto `root`, so this strip cannot fail today. It
    // is still an error rather than an `expect`: this runs inside an IPC
    // command, and turning a future bug in pass 1 into a rejected request beats
    // turning it into a panic on Tauri's main thread.
    let Ok(relative) = resolved.strip_prefix(root) else {
        bail!("path escapes the workspace");
    };
    if policy == SymlinkPolicy::Forbid {
        let mut walk = root.to_path_buf();
        for component in relative.components() {
            walk.push(component);
            if let Ok(meta) = fs::symlink_metadata(&walk) {
                if meta.file_type().is_symlink() {
                    bail!(
                        "`{}` is a symlink; symlinks are not allowed inside the workspace",
                        walk.strip_prefix(root).unwrap_or(&walk).display()
                    );
                }
            }
        }
    }

    // Pass 3: canonicalize the deepest existing ancestor and re-check containment.
    let mut anchor: &Path = resolved.as_path();
    let existing = loop {
        if anchor.symlink_metadata().is_ok() {
            break anchor;
        }
        match anchor.parent() {
            Some(parent) if parent.starts_with(root) || parent == root => anchor = parent,
            _ => break root,
        }
    };
    let canonical = fs::canonicalize(existing)
        .with_context(|| format!("could not canonicalize {}", existing.display()))?;
    if canonical != root && !canonical.starts_with(root) {
        bail!("path escapes the workspace");
    }

    // With symlinks permitted, containment of the deepest *existing* ancestor is
    // not enough on its own: `link -> /etc` inside the root has an ancestor that
    // is contained while the target is not. Canonicalize the target itself and
    // re-check whenever it exists.
    if policy == SymlinkPolicy::AllowInternal {
        if let Ok(target) = fs::canonicalize(&resolved) {
            if target != root && !target.starts_with(root) {
                bail!("path resolves outside the granted directory");
            }
        }
    }

    Ok(resolved)
}

/// Normalize an absolute in-workspace path back into the `/`-separated relative
/// form the frontend speaks.
fn to_relative(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .components()
        .filter_map(|c| match c {
            Component::Normal(part) => part.to_str(),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join("/")
}

pub fn list(root: &Path, rel: &str) -> Result<Vec<FileEntry>> {
    let dir = resolve(root, rel)?;
    let meta =
        fs::metadata(&dir).with_context(|| format!("`{}` does not exist in the workspace", rel))?;
    if !meta.is_dir() {
        bail!("`{}` is not a directory", rel);
    }

    let mut entries = Vec::new();
    for entry in fs::read_dir(&dir).with_context(|| format!("could not read `{}`", rel))? {
        let entry = entry.context("could not read a directory entry")?;
        let file_type = entry
            .file_type()
            .context("could not stat a directory entry")?;
        // Symlinks are unreachable through read/write, so don't advertise them.
        if file_type.is_symlink() {
            continue;
        }
        let Some(name) = entry.file_name().to_str().map(str::to_owned) else {
            continue;
        };
        entries.push(FileEntry {
            path: to_relative(root, &entry.path()),
            name,
            is_dir: file_type.is_dir(),
        });
    }

    // Directories first, then case-insensitive name order.
    entries.sort_by(|a, b| {
        b.is_dir
            .cmp(&a.is_dir)
            .then_with(|| a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });
    Ok(entries)
}

pub fn read(root: &Path, rel: &str) -> Result<String> {
    let path = resolve(root, rel)?;
    let meta = fs::metadata(&path)
        .with_context(|| format!("`{}` does not exist in the workspace", rel))?;
    if !meta.is_file() {
        bail!("`{}` is not a file", rel);
    }
    if meta.len() > MAX_READ_BYTES {
        bail!(
            "`{}` is {} bytes; the editor only opens files up to {} bytes",
            rel,
            meta.len(),
            MAX_READ_BYTES
        );
    }
    let bytes = fs::read(&path).with_context(|| format!("could not read `{}`", rel))?;
    String::from_utf8(bytes).map_err(|_| anyhow!("`{}` is not valid UTF-8 text", rel))
}

pub fn write(root: &Path, rel: &str, contents: &str) -> Result<()> {
    if contents.len() > MAX_WRITE_BYTES {
        bail!(
            "refusing to write {} bytes; the limit is {} bytes",
            contents.len(),
            MAX_WRITE_BYTES
        );
    }
    let path = resolve(root, rel)?;
    if path == root {
        bail!("the workspace root is not a file");
    }
    if path.is_dir() {
        bail!("`{}` is a directory", rel);
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("could not create the parent directory of `{}`", rel))?;
    }
    fs::write(&path, contents).with_context(|| format!("could not write `{}`", rel))
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn workspace_root(app: AppHandle) -> Result<String, String> {
    let root = ensure_root(&app).map_err(|e| format!("{e:#}"))?;
    Ok(root.to_string_lossy().into_owned())
}

#[tauri::command]
pub fn workspace_list(app: AppHandle, rel: String) -> Result<Vec<FileEntry>, String> {
    let root = ensure_root(&app).map_err(|e| format!("{e:#}"))?;
    list(&root, &rel).map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn workspace_read(app: AppHandle, rel: String) -> Result<String, String> {
    let root = ensure_root(&app).map_err(|e| format!("{e:#}"))?;
    read(&root, &rel).map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn workspace_write(app: AppHandle, rel: String, contents: String) -> Result<(), String> {
    let root = ensure_root(&app).map_err(|e| format!("{e:#}"))?;
    write(&root, &rel, &contents).map_err(|e| format!("{e:#}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("learn-workspace-test-{name}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        fs::canonicalize(&dir).unwrap()
    }

    #[test]
    fn accepts_plain_relative_paths() {
        let root = scratch("plain");
        assert_eq!(
            resolve(&root, "a/b.py").unwrap(),
            root.join("a").join("b.py")
        );
        assert_eq!(resolve(&root, "./a").unwrap(), root.join("a"));
        assert_eq!(resolve(&root, "").unwrap(), root);
    }

    /// A leading dot is an ordinary filename, not the `.` component.
    ///
    /// The app writes `.exercise-version` beside the learner's `solution.py` to
    /// record which build of the exercise the workspace was last written from.
    /// If that write were rejected here, the app would lose its only way to
    /// notice an exercise changed under work already on disk, and it would lose
    /// it silently, which is the failure the stamp exists to prevent.
    #[test]
    fn accepts_dotfiles() {
        let root = scratch("dotfile");
        assert_eq!(
            resolve(&root, "exercises/tool-use/react-loop/.exercise-version").unwrap(),
            root.join("exercises")
                .join("tool-use")
                .join("react-loop")
                .join(".exercise-version")
        );
        assert_eq!(resolve(&root, ".hidden").unwrap(), root.join(".hidden"));
        // Still only the exact `.` component is a no-op, and `..` is still out.
        assert_eq!(resolve(&root, "./.hidden").unwrap(), root.join(".hidden"));
        assert!(resolve(&root, "../.hidden").is_err());
    }

    #[test]
    fn rejects_parent_traversal() {
        let root = scratch("traversal");
        for bad in ["..", "../etc/passwd", "a/../../b", "ok/../.."] {
            assert!(
                resolve(&root, bad).is_err(),
                "expected `{bad}` to be rejected"
            );
        }
    }

    #[test]
    fn rejects_absolute_paths() {
        let root = scratch("absolute");
        for bad in ["/etc/passwd", "/", "//tmp/x"] {
            assert!(
                resolve(&root, bad).is_err(),
                "expected `{bad}` to be rejected"
            );
        }
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlink_escape() {
        let root = scratch("symlink");
        std::os::unix::fs::symlink("/etc", root.join("escape")).unwrap();
        assert!(resolve(&root, "escape").is_err());
        assert!(resolve(&root, "escape/passwd").is_err());
    }

    /// The escape guard, exercised through *every* entry point rather than
    /// through `resolve` alone — a hole in any one of `list`/`read`/`write` is
    /// as good as no guard at all.
    ///
    /// Covers the three shapes an attacker-controlled `rel` can take: `..`
    /// traversal, an absolute path, and a symlink inside the workspace that
    /// points out of it.
    #[cfg(unix)]
    #[test]
    fn path_escape_guard_blocks_dotdot_absolute_and_symlink() {
        let root = scratch("escape-guard");
        let outside = scratch("escape-guard-outside");
        fs::write(outside.join("secret.txt"), "token=hunter2\n").unwrap();
        std::os::unix::fs::symlink(&outside, root.join("escape")).unwrap();

        let absolute_secret = outside.join("secret.txt").display().to_string();
        let absolute_dir = outside.display().to_string();
        // The real name of the sibling directory, so the `..` attempts below
        // are genuine escapes rather than paths that would 404 anyway.
        let sibling = outside
            .file_name()
            .and_then(|n| n.to_str())
            .expect("scratch dirs have UTF-8 names")
            .to_string();
        let attempts = [
            // 1. parent traversal, plain and laundered through a real segment
            "..".to_string(),
            format!("../{sibling}/secret.txt"),
            format!("exercises/../../{sibling}/secret.txt"),
            "ok/../..".to_string(),
            // 2. absolute paths, including one that names the real target
            absolute_secret.clone(),
            absolute_dir.clone(),
            "/etc/passwd".to_string(),
            // 3. an in-workspace symlink pointing outside, used as both the
            //    target and as an intermediate directory component
            "escape".to_string(),
            "escape/secret.txt".to_string(),
            "escape/nested/deeper.txt".to_string(),
        ];

        for rel in &attempts {
            assert!(resolve(&root, rel).is_err(), "resolve accepted `{rel}`");
            assert!(read(&root, rel).is_err(), "read accepted `{rel}`");
            assert!(list(&root, rel).is_err(), "list accepted `{rel}`");
            assert!(
                write(&root, rel, "pwned").is_err(),
                "write accepted `{rel}`"
            );
        }

        // Nothing leaked out and nothing was clobbered on the way past.
        assert_eq!(
            fs::read_to_string(outside.join("secret.txt")).unwrap(),
            "token=hunter2\n"
        );
        assert!(!outside.join("nested").exists());
        // The symlink itself is not even advertised in a listing.
        assert!(list(&root, "").unwrap().iter().all(|e| e.name != "escape"));
    }

    #[test]
    fn write_then_read_roundtrips() {
        let root = scratch("roundtrip");
        write(&root, "nested/hello.py", "print('hi')\n").unwrap();
        assert_eq!(read(&root, "nested/hello.py").unwrap(), "print('hi')\n");
        let entries = list(&root, "").unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].name, "nested");
        assert!(entries[0].is_dir);
    }

    #[test]
    fn file_entry_ships_both_casings_of_the_dir_flag() {
        let json = serde_json::to_value(FileEntry {
            name: "exercises".into(),
            path: "exercises".into(),
            is_dir: true,
        })
        .unwrap();
        assert_eq!(json["name"], "exercises");
        assert_eq!(json["path"], "exercises");
        assert_eq!(json["is_dir"], true);
        assert_eq!(json["isDir"], true);
    }

    #[test]
    fn rejects_oversized_write() {
        let root = scratch("oversize");
        let payload = "x".repeat(MAX_WRITE_BYTES + 1);
        assert!(write(&root, "big.txt", &payload).is_err());
    }
}
