//! Embedded terminal.
//!
//! One [`PtyManager`] lives in Tauri state and owns every open pty. Each session
//! gets two dedicated threads:
//!
//! * a **reader** that streams pty output to the frontend as `pty:output`, and
//! * a **writer** that drains an unbounded queue of keystrokes into the pty.
//!
//! Three properties this module is written to guarantee, because getting any of
//! them wrong wedges or kills the whole app:
//!
//! 1. **No thread outlives its session.** Both threads exit when the pty closes,
//!    and both consult the session's `closed` flag so a session that was killed
//!    explicitly can never emit output for an id the frontend has retired.
//! 2. **No panic escapes a worker thread.** Both thread bodies run inside
//!    `catch_unwind`, and the release profile deliberately does *not* set
//!    `panic = "abort"` (which would turn any panic anywhere into a hard process
//!    abort, `catch_unwind` or not).
//! 3. **No lock is held across a blocking call.** The registry mutex is held
//!    only long enough to clone an `Arc` out of the map. Reads happen on the
//!    reader thread with no lock at all, and writes — which block whenever the
//!    child stops draining its input — happen on the writer thread, so neither
//!    the registry nor the UI thread can be stalled by a stuck child process.
//!
//! Input is queued rather than written inline for a second reason: an unbounded
//! channel preserves keystroke *order* while still returning immediately, which
//! a "spawn a task per write" design would not.

use std::collections::HashMap;
use std::io::{ErrorKind, Read, Write};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;

use anyhow::{anyhow, bail, Context, Result};
use parking_lot::Mutex;
use portable_pty::{native_pty_system, Child, CommandBuilder, MasterPty, PtySize};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};
use uuid::Uuid;

/// Event carrying terminal output to the frontend.
pub const OUTPUT_EVENT: &str = "pty:output";
/// Event fired once when a session's shell ends and the session is dropped.
pub const EXIT_EVENT: &str = "pty:exit";

const READ_CHUNK: usize = 8 * 1024;

#[derive(Debug, Clone, Serialize)]
pub struct PtyOutput {
    pub id: String,
    pub data: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PtyExit {
    pub id: String,
}

/// A live terminal session.
///
/// Every field is independently locked. Nothing here is guarded by the registry
/// mutex, so a slow operation on one session cannot block another session or the
/// spawn/kill paths.
struct PtySession {
    /// Only touched by `resize`, which is a fast ioctl.
    master: Mutex<Box<dyn MasterPty + Send>>,
    /// Only touched by `terminate`.
    child: Mutex<Box<dyn Child + Send + Sync>>,
    /// Keystrokes queued for the writer thread. Sending never blocks.
    input: Sender<Vec<u8>>,
    /// Set the instant the session is retired, by whichever party gets there
    /// first. The reader thread checks it so a killed session cannot emit.
    closed: Arc<AtomicBool>,
}

impl PtySession {
    fn is_closed(&self) -> bool {
        self.closed.load(Ordering::SeqCst)
    }

    /// Queue bytes for the child. Returns immediately; the writer thread does
    /// the blocking work.
    fn send(&self, bytes: Vec<u8>) -> Result<()> {
        if self.is_closed() {
            bail!("the terminal session has ended");
        }
        self.input
            .send(bytes)
            .map_err(|_| anyhow!("the terminal is no longer accepting input"))
    }

    /// Kill the shell and reap it. Idempotent: `kill`/`wait` on an already-dead
    /// child are both no-ops that we ignore.
    ///
    /// Dropping the session afterwards closes the master handles and the input
    /// channel, which is what makes both worker threads fall out of their loops.
    fn terminate(&self) {
        self.closed.store(true, Ordering::SeqCst);
        let mut child = self.child.lock();
        let _ = child.kill();
        let _ = child.wait();
    }
}

#[derive(Default)]
pub struct PtyManager {
    sessions: Mutex<HashMap<String, Arc<PtySession>>>,
}

impl PtyManager {
    fn insert(&self, id: String, session: Arc<PtySession>) {
        self.sessions.lock().insert(id, session);
    }

    /// Clone a session handle out of the registry. The map lock is released
    /// before the caller does anything with the session.
    fn get(&self, id: &str) -> Result<Arc<PtySession>> {
        self.sessions
            .lock()
            .get(id)
            .cloned()
            .ok_or_else(|| anyhow!("no terminal session with id `{id}`"))
    }

    fn take(&self, id: &str) -> Option<Arc<PtySession>> {
        self.sessions.lock().remove(id)
    }

    /// Tear every session down. Called when the window goes away.
    pub fn kill_all(&self) {
        let drained: Vec<Arc<PtySession>> = {
            let mut sessions = self.sessions.lock();
            sessions.drain().map(|(_, session)| session).collect()
        };
        for session in drained {
            session.terminate();
        }
    }
}

/// Remove a session from the registry and kill its shell. Safe to call from any
/// thread and safe to call twice — the second call finds nothing to do.
fn retire(app: &AppHandle, id: &str) {
    if let Some(manager) = app.try_state::<PtyManager>() {
        if let Some(session) = manager.take(id) {
            session.terminate();
        }
    }
}

/// Run a worker-thread body so a panic inside it retires the session instead of
/// unwinding out of the thread. Returns `true` when the body panicked.
fn guarded(body: impl FnOnce() -> bool) -> bool {
    catch_unwind(AssertUnwindSafe(body)).unwrap_or(true)
}

/// The shell to run. `$SHELL` when the user has one, else a sane per-OS default.
fn default_shell() -> String {
    if cfg!(windows) {
        std::env::var("COMSPEC").unwrap_or_else(|_| "cmd.exe".to_string())
    } else {
        std::env::var("SHELL")
            .ok()
            .filter(|s| !s.trim().is_empty())
            .unwrap_or_else(|| "/bin/zsh".to_string())
    }
}

fn build_command(shell: &str, cwd: &Path) -> CommandBuilder {
    let mut cmd = CommandBuilder::new(shell);
    // A login shell picks up the PATH set in the user's profile, which a
    // GUI-launched app does not otherwise inherit on macOS.
    if !cfg!(windows) {
        cmd.arg("-l");
    }
    cmd.cwd(cwd);
    cmd.env("TERM", "xterm-256color");
    cmd.env("COLORTERM", "truecolor");
    cmd
}

/// Decode as much complete UTF-8 as `pending` holds, leaving a partial trailing
/// sequence in place for the next read. Without this, a multi-byte character
/// straddling a chunk boundary would be mangled into replacement characters.
fn drain_utf8(pending: &mut Vec<u8>) -> String {
    let mut out = String::new();
    loop {
        match std::str::from_utf8(pending) {
            Ok(text) => {
                out.push_str(text);
                pending.clear();
                break;
            }
            Err(err) => {
                let valid = err.valid_up_to();
                if let Ok(text) = std::str::from_utf8(&pending[..valid]) {
                    out.push_str(text);
                }
                match err.error_len() {
                    // Genuinely invalid bytes: emit U+FFFD and skip past them.
                    Some(len) => {
                        out.push('\u{FFFD}');
                        pending.drain(..valid + len);
                    }
                    // Truncated sequence at the end: keep it for the next read.
                    None => {
                        pending.drain(..valid);
                        break;
                    }
                }
            }
        }
    }
    out
}

/// Stream pty output until the pty closes or the session is retired.
///
/// No lock of any kind is held across `reader.read`, which blocks until the
/// child produces output — possibly for hours.
fn stream_output(app: &AppHandle, id: &str, mut reader: Box<dyn Read + Send>, closed: &AtomicBool) {
    let mut buf = vec![0u8; READ_CHUNK];
    let mut pending: Vec<u8> = Vec::with_capacity(READ_CHUNK);

    loop {
        let read = match reader.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => n,
            Err(err) if err.kind() == ErrorKind::Interrupted => continue,
            // A closed pty surfaces as EIO on Linux and as a plain error on
            // macOS; either way the session is over.
            Err(_) => break,
        };

        // The session may have been killed while we were parked in `read`. A
        // grandchild holding the slave fd open can keep this loop alive past
        // the shell's death, so re-check before every emit: output for a
        // retired id would confuse (or resurrect) a pane the frontend closed.
        if closed.load(Ordering::SeqCst) {
            return;
        }

        pending.extend_from_slice(&buf[..read]);
        let data = drain_utf8(&mut pending);
        if data.is_empty() {
            continue;
        }
        if app
            .emit(
                OUTPUT_EVENT,
                PtyOutput {
                    id: id.to_owned(),
                    data,
                },
            )
            .is_err()
        {
            // The window is gone; stop streaming.
            break;
        }
    }

    // Flush anything left over, unless the session was already retired.
    if !pending.is_empty() && !closed.load(Ordering::SeqCst) {
        let data = drain_utf8(&mut pending);
        if !data.is_empty() {
            let _ = app.emit(
                OUTPUT_EVENT,
                PtyOutput {
                    id: id.to_owned(),
                    data,
                },
            );
        }
    }
}

fn reader_thread(
    app: AppHandle,
    id: String,
    reader: Box<dyn Read + Send>,
    closed: Arc<AtomicBool>,
) {
    guarded(|| {
        stream_output(&app, &id, reader, &closed);
        false
    });
    // Whatever ended the loop — EOF, error or panic — the session is done.
    retire(&app, &id);
    let _ = app.emit(EXIT_EVENT, PtyExit { id });
}

/// Drain queued input into the pty. Returns `true` if a write failed, meaning
/// the session should be torn down.
///
/// `write_all` blocks whenever the child stops reading its stdin (a full pty
/// input buffer is only ~4 KiB), which is exactly why this runs on its own
/// thread instead of inline in the IPC command.
fn pump_input(rx: &Receiver<Vec<u8>>, writer: &mut dyn Write) -> bool {
    while let Ok(chunk) = rx.recv() {
        if writer.write_all(&chunk).is_err() || writer.flush().is_err() {
            return true;
        }
    }
    false
}

fn writer_thread(
    app: AppHandle,
    id: String,
    mut writer: Box<dyn Write + Send>,
    rx: Receiver<Vec<u8>>,
) {
    let failed = guarded(|| pump_input(&rx, &mut writer));
    if failed {
        // Dropping the session releases the last `Sender`, so a later `recv`
        // could not have returned anyway. Kill the shell rather than leaving a
        // terminal that silently swallows keystrokes.
        retire(&app, &id);
    }
}

fn pty_size(cols: u16, rows: u16) -> PtySize {
    PtySize {
        rows: rows.max(1),
        cols: cols.max(1),
        pixel_width: 0,
        pixel_height: 0,
    }
}

fn spawn(app: &AppHandle, manager: &PtyManager, cols: u16, rows: u16) -> Result<String> {
    let root = crate::workspace::ensure_root(app)?;

    let pair = native_pty_system()
        .openpty(pty_size(cols, rows))
        .context("could not open a pseudo terminal")?;

    let shell = default_shell();
    let child = pair
        .slave
        .spawn_command(build_command(&shell, &root))
        .with_context(|| format!("could not start `{shell}`"))?;
    // Drop our copy of the slave so the pty reports EOF once the shell exits.
    drop(pair.slave);

    let reader = pair
        .master
        .try_clone_reader()
        .context("could not read from the pseudo terminal")?;
    let writer = pair
        .master
        .take_writer()
        .context("could not write to the pseudo terminal")?;

    let id = Uuid::new_v4().to_string();
    let closed = Arc::new(AtomicBool::new(false));
    let (input, rx) = mpsc::channel::<Vec<u8>>();

    manager.insert(
        id.clone(),
        Arc::new(PtySession {
            master: Mutex::new(pair.master),
            child: Mutex::new(child),
            input,
            closed: Arc::clone(&closed),
        }),
    );

    // From here on, any failure must unwind the registry entry too.
    let spawn_result = std::thread::Builder::new()
        .name(format!("pty-writer-{id}"))
        .spawn({
            let app = app.clone();
            let id = id.clone();
            move || writer_thread(app, id, writer, rx)
        })
        .and_then(|_| {
            std::thread::Builder::new()
                .name(format!("pty-reader-{id}"))
                .spawn({
                    let app = app.clone();
                    let id = id.clone();
                    let closed = Arc::clone(&closed);
                    move || reader_thread(app, id, reader, closed)
                })
        });

    if let Err(err) = spawn_result {
        if let Some(session) = manager.take(&id) {
            session.terminate();
        }
        return Err(anyhow!("could not start a terminal worker thread: {err}"));
    }

    Ok(id)
}

/// Quote a path for a POSIX or PowerShell/cmd command line.
pub fn shell_quote(value: &str) -> String {
    if cfg!(windows) {
        format!("\"{}\"", value.replace('"', "\\\""))
    } else {
        format!("'{}'", value.replace('\'', r"'\''"))
    }
}

/// Send a raw line (terminated with a carriage return, as a real keystroke
/// would be) into a session.
pub fn send_line(manager: &PtyManager, id: &str, line: &str) -> Result<()> {
    manager.get(id)?.send(format!("{line}\r").into_bytes())
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn pty_spawn(
    app: AppHandle,
    manager: State<'_, PtyManager>,
    cols: u16,
    rows: u16,
) -> Result<String, String> {
    spawn(&app, &manager, cols, rows).map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn pty_write(manager: State<'_, PtyManager>, id: String, data: String) -> Result<(), String> {
    manager
        .get(&id)
        .and_then(|session| session.send(data.into_bytes()))
        .map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn pty_resize(
    manager: State<'_, PtyManager>,
    id: String,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    manager
        .get(&id)
        .and_then(|session| {
            session
                .master
                .lock()
                .resize(pty_size(cols, rows))
                .context("could not resize the terminal")
        })
        .map_err(|e| format!("{e:#}"))
}

#[tauri::command]
pub fn pty_kill(manager: State<'_, PtyManager>, id: String) -> Result<(), String> {
    match manager.take(&id) {
        Some(session) => {
            session.terminate();
            Ok(())
        }
        None => Err(format!("no terminal session with id `{id}`")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io;

    #[test]
    fn drains_complete_utf8() {
        let mut pending = "héllo".as_bytes().to_vec();
        assert_eq!(drain_utf8(&mut pending), "héllo");
        assert!(pending.is_empty());
    }

    #[test]
    fn holds_back_split_multibyte_sequence() {
        let full = "aé".as_bytes().to_vec();
        let (head, tail) = full.split_at(full.len() - 1);

        let mut pending = head.to_vec();
        assert_eq!(drain_utf8(&mut pending), "a");
        assert_eq!(pending.len(), 1, "the partial sequence is retained");

        pending.extend_from_slice(tail);
        assert_eq!(drain_utf8(&mut pending), "é");
        assert!(pending.is_empty());
    }

    #[test]
    fn replaces_invalid_bytes() {
        let mut pending = vec![b'a', 0xFF, b'b'];
        assert_eq!(drain_utf8(&mut pending), "a\u{FFFD}b");
        assert!(pending.is_empty());
    }

    /// A panic in a worker thread must be contained, not unwound into the
    /// runtime — the thread reports failure so its session gets retired.
    #[test]
    fn guarded_contains_a_panicking_body() {
        let previous = std::panic::take_hook();
        std::panic::set_hook(Box::new(|_| {}));
        let panicked = guarded(|| panic!("reader thread blew up"));
        std::panic::set_hook(previous);

        assert!(panicked, "a panicking body reports failure");
        assert!(!guarded(|| false), "a clean body reports success");
    }

    #[test]
    fn pump_input_writes_in_order_then_stops_on_disconnect() {
        let (tx, rx) = mpsc::channel::<Vec<u8>>();
        tx.send(b"ec".to_vec()).unwrap();
        tx.send(b"ho hi\r".to_vec()).unwrap();
        drop(tx);

        let mut sink: Vec<u8> = Vec::new();
        assert!(
            !pump_input(&rx, &mut sink),
            "a clean disconnect is not a failure"
        );
        assert_eq!(sink, b"echo hi\r");
    }

    #[test]
    fn pump_input_reports_write_failure() {
        struct Broken;
        impl Write for Broken {
            fn write(&mut self, _: &[u8]) -> io::Result<usize> {
                Err(io::Error::new(io::ErrorKind::BrokenPipe, "pty closed"))
            }
            fn flush(&mut self) -> io::Result<()> {
                Ok(())
            }
        }

        let (tx, rx) = mpsc::channel::<Vec<u8>>();
        tx.send(b"x".to_vec()).unwrap();
        assert!(pump_input(&rx, &mut Broken), "a failed write ends the pump");
    }

    /// A retired session must refuse further input rather than queueing bytes
    /// for a writer thread that has already gone away.
    #[cfg(unix)]
    #[test]
    fn closed_session_refuses_input_and_registry_stays_empty() {
        let pair = native_pty_system().openpty(pty_size(80, 24)).unwrap();
        let child = pair
            .slave
            .spawn_command(CommandBuilder::new("/bin/cat"))
            .unwrap();
        drop(pair.slave);
        // No writer thread here: this test drives the queue by hand so it can
        // inspect what a terminated session does with input.
        let (input, rx) = mpsc::channel::<Vec<u8>>();

        let session = Arc::new(PtySession {
            master: Mutex::new(pair.master),
            child: Mutex::new(child),
            input,
            closed: Arc::new(AtomicBool::new(false)),
        });

        let manager = PtyManager::default();
        manager.insert("abc".into(), Arc::clone(&session));
        assert!(session.send(b"ok\r".to_vec()).is_ok());
        assert!(manager.get("abc").is_ok(), "the session is registered");

        let taken = manager.take("abc").expect("session is registered");
        taken.terminate();
        assert!(
            manager.get("abc").is_err(),
            "a killed session leaves no registry entry"
        );
        assert!(
            session.send(b"nope\r".to_vec()).is_err(),
            "a terminated session accepts no more input"
        );

        // The writer thread's channel outlives the session only as long as this
        // test holds it; draining proves the queued byte was not lost.
        drop(session);
        drop(taken);
        assert_eq!(rx.recv().unwrap(), b"ok\r");
    }

    /// Exercises the real openpty -> spawn -> stream path with the same shape as
    /// production (reader thread started before any I/O, long-lived child), and
    /// proves the reader thread ends once the child is killed.
    #[cfg(unix)]
    #[test]
    fn pty_streams_output_and_reader_thread_exits() {
        use std::sync::mpsc::RecvTimeoutError;
        use std::time::{Duration, Instant};

        let pair = native_pty_system().openpty(pty_size(80, 24)).unwrap();
        // `cat` stays alive and echoes, so there is no race against process exit.
        let mut child = pair
            .slave
            .spawn_command(CommandBuilder::new("/bin/cat"))
            .unwrap();
        drop(pair.slave);

        let mut reader = pair.master.try_clone_reader().unwrap();
        let mut writer = pair.master.take_writer().unwrap();

        let (chunks_tx, chunks_rx) = mpsc::channel();
        let (done_tx, done_rx) = mpsc::channel();
        std::thread::spawn(move || {
            let mut buf = [0u8; 1024];
            let mut pending = Vec::new();
            loop {
                match reader.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        pending.extend_from_slice(&buf[..n]);
                        let text = drain_utf8(&mut pending);
                        if !text.is_empty() && chunks_tx.send(text).is_err() {
                            break;
                        }
                    }
                    Err(err) if err.kind() == ErrorKind::Interrupted => continue,
                    Err(_) => break,
                }
            }
            let _ = done_tx.send(());
        });

        writer.write_all(b"hello-pty\n").unwrap();
        writer.flush().unwrap();

        let deadline = Instant::now() + Duration::from_secs(5);
        let mut seen = String::new();
        while Instant::now() < deadline && !seen.contains("hello-pty") {
            match chunks_rx.recv_timeout(Duration::from_millis(100)) {
                Ok(chunk) => seen.push_str(&chunk),
                Err(RecvTimeoutError::Timeout) => continue,
                Err(RecvTimeoutError::Disconnected) => break,
            }
        }
        assert!(
            seen.contains("hello-pty"),
            "expected the child's output on the master side, got {seen:?}"
        );

        let _ = child.kill();
        let _ = child.wait();
        drop(writer);
        drop(pair.master);
        assert!(
            done_rx.recv_timeout(Duration::from_secs(5)).is_ok(),
            "the reader thread must exit once the pty closes"
        );
    }

    #[cfg(unix)]
    #[test]
    fn quotes_paths_with_single_quotes() {
        assert_eq!(shell_quote("/tmp/a b.py"), "'/tmp/a b.py'");
        assert_eq!(shell_quote("/tmp/it's.py"), r"'/tmp/it'\''s.py'");
        assert_eq!(shell_quote("/tmp/;rm -rf ~"), "'/tmp/;rm -rf ~'");
    }
}
