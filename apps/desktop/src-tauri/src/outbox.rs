//! The offline outbox.
//!
//! Grading happens here, on the learner's machine, so the most reward-worthy
//! event in the product happens on the device least able to report it. This is
//! what makes the report survive a closed laptop, a dead wifi connection, and an
//! account that did not exist yet when the work was done.
//!
//! It holds domain events, never XP. The events are the request bodies of the
//! two API routes that already exist, so this is those calls made durable and
//! ordered rather than a second wire format that has to be kept in step with
//! them. The server decides what anything is worth.
//!
//! ## Why a file, and why here
//!
//! Not the webview's localStorage: it can be evicted under storage pressure, and
//! losing a month of offline work to a cache eviction is not a trade worth
//! making. It is also synchronous, so draining two thousand events would block
//! the render thread.
//!
//! Not the exercise sandbox either. `workspace.rs` seeds that directory with a
//! README saying everything in it belongs to the learner, and an app-owned
//! journal in a folder people are invited to `rm -rf` is wrong twice over.
//!
//! So: app-data, beside the other app-owned files. `project.rs` already builds
//! `app_data_dir().join("project.json")` without going through
//! `workspace::resolve`, and for the same reason this does: the path has no
//! caller-supplied component. No path string crosses the IPC boundary in either
//! direction.
//!
//! ## Why JSONL
//!
//! Appending is one write. A crash mid-append loses the tail line, which fails
//! to parse and is skipped. Rewriting a whole JSON array on every event risks
//! losing the entire file instead of one line.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Runtime};

/// Keep the newest events and drop the oldest. Attempts are the high-volume
/// event and most of them are failures; a queue that grows without bound is a
/// disk leak with extra steps.
const MAX_EVENTS: usize = 2000;

/// One queued event. `payload` is verbatim the body of the route it names.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutboxEvent {
    /// Client-generated, and sent along so replaying a batch does not duplicate
    /// the attempt log. Award keys dedupe the XP; they do not dedupe history.
    #[serde(rename = "clientEventId")]
    pub client_event_id: String,
    pub kind: String,
    /// Client clock. Evidence, not authority: the server clamps it and assigns
    /// the day itself.
    #[serde(rename = "occurredAt")]
    pub occurred_at: String,
    /// Strictly increasing per install, so a drain preserves order. A completion
    /// followed by an un-completion, replayed the other way round, leaves the
    /// lesson in the wrong state.
    pub seq: u64,
    pub payload: serde_json::Value,
}

fn outbox_path<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf> {
    let dir = app
        .path()
        .app_data_dir()
        .context("could not determine the application data directory")?;
    fs::create_dir_all(&dir).with_context(|| format!("could not create {}", dir.display()))?;
    Ok(dir.join("outbox.jsonl"))
}

/// Every event still queued, oldest first.
///
/// A line that will not parse is skipped rather than fatal: it is either a
/// half-written tail from a crash or a leftover from an older shape, and neither
/// is worth refusing to sync over.
pub fn read_all(path: &PathBuf) -> Vec<OutboxEvent> {
    let raw = match fs::read_to_string(path) {
        Ok(raw) => raw,
        Err(_) => return Vec::new(),
    };
    raw.lines()
        .filter(|line| !line.trim().is_empty())
        .filter_map(|line| serde_json::from_str::<OutboxEvent>(line).ok())
        .collect()
}

pub fn append(path: &PathBuf, event: &OutboxEvent) -> Result<()> {
    let line = serde_json::to_string(event).context("could not encode the event")?;
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .with_context(|| format!("could not open {}", path.display()))?;
    writeln!(file, "{line}").context("could not append to the outbox")?;

    // Trimming is a rewrite, so it happens only when the queue is actually over
    // the cap rather than on every append.
    let events = read_all(path);
    if events.len() > MAX_EVENTS {
        rewrite(path, &events[events.len() - MAX_EVENTS..])?;
    }
    Ok(())
}

/// Compaction goes through a temp file and a rename, so a crash halfway leaves
/// the old file intact rather than a truncated one.
pub fn rewrite(path: &PathBuf, events: &[OutboxEvent]) -> Result<()> {
    let temp = path.with_extension("jsonl.tmp");
    let mut body = String::new();
    for event in events {
        body.push_str(&serde_json::to_string(event).context("could not encode the event")?);
        body.push('\n');
    }
    fs::write(&temp, body).with_context(|| format!("could not write {}", temp.display()))?;
    fs::rename(&temp, path).with_context(|| format!("could not replace {}", path.display()))?;
    Ok(())
}

/// Forget the events the server accepted, keeping everything else.
pub fn ack(path: &PathBuf, acked: &[String]) -> Result<()> {
    let keep: Vec<OutboxEvent> = read_all(path)
        .into_iter()
        .filter(|event| !acked.contains(&event.client_event_id))
        .collect();
    if keep.is_empty() {
        let _ = fs::remove_file(path);
        return Ok(());
    }
    rewrite(path, &keep)
}

pub fn next_seq(path: &PathBuf) -> u64 {
    read_all(path).last().map(|event| event.seq + 1).unwrap_or(0)
}

pub fn path_for<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf> {
    outbox_path(app)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn event(id: &str, seq: u64) -> OutboxEvent {
        OutboxEvent {
            client_event_id: id.into(),
            kind: "lesson.progress".into(),
            occurred_at: "2026-08-23T10:00:00.000Z".into(),
            seq,
            payload: serde_json::json!({ "lessonId": "a.b" }),
        }
    }

    #[test]
    fn appends_and_reads_back_in_order() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        for (i, id) in ["a", "b", "c"].iter().enumerate() {
            append(&path, &event(id, i as u64)).unwrap();
        }

        let events = read_all(&path);
        assert_eq!(events.len(), 3);
        assert_eq!(events[0].client_event_id, "a");
        assert_eq!(events[2].client_event_id, "c");
        assert!(events.windows(2).all(|w| w[0].seq < w[1].seq));
    }

    #[test]
    fn a_half_written_line_is_skipped_not_fatal() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        append(&path, &event("a", 0)).unwrap();
        // What a crash mid-append leaves behind.
        let mut file = OpenOptions::new().append(true).open(&path).unwrap();
        write!(file, "{{\"clientEventId\":\"b\",\"kin").unwrap();
        drop(file);

        let events = read_all(&path);
        assert_eq!(events.len(), 1, "the good line survives");
        assert_eq!(events[0].client_event_id, "a");
    }

    #[test]
    fn ack_forgets_only_what_was_accepted() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        for (i, id) in ["a", "b", "c"].iter().enumerate() {
            append(&path, &event(id, i as u64)).unwrap();
        }

        ack(&path, &["a".to_string(), "c".to_string()]).unwrap();
        let left = read_all(&path);
        assert_eq!(left.len(), 1);
        assert_eq!(left[0].client_event_id, "b");
    }

    #[test]
    fn acking_everything_removes_the_file() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        append(&path, &event("a", 0)).unwrap();
        ack(&path, &["a".to_string()]).unwrap();
        assert!(!path.exists());
        assert!(read_all(&path).is_empty(), "a missing file reads as empty");
    }

    #[test]
    fn the_queue_is_bounded_and_keeps_the_newest() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        for i in 0..(MAX_EVENTS + 50) {
            append(&path, &event(&format!("e{i}"), i as u64)).unwrap();
        }

        let events = read_all(&path);
        assert_eq!(events.len(), MAX_EVENTS);
        assert_eq!(
            events.last().unwrap().client_event_id,
            format!("e{}", MAX_EVENTS + 49),
            "the newest event survives"
        );
        assert_eq!(events[0].client_event_id, "e50", "the oldest are dropped");
    }

    #[test]
    fn seq_continues_across_restarts() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("outbox.jsonl");
        assert_eq!(next_seq(&path), 0, "an empty queue starts at zero");

        append(&path, &event("a", next_seq(&path))).unwrap();
        append(&path, &event("b", next_seq(&path))).unwrap();
        assert_eq!(next_seq(&path), 2);
    }
}
