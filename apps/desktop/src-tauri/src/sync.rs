//! Talking to the API, from Rust.
//!
//! The bearer token never enters the webview. The frontend asks for a sync and
//! is told what happened; it is never handed the credential to do it itself.
//! That is not paranoia about our own JavaScript, it is that a token in page
//! memory is reachable by anything that ever manages to run in that page, and
//! there is no reason for it to be there.
//!
//! These are narrow commands against a base URL fixed at build time, not a
//! general HTTP bridge. A user-editable API base would be a token exfiltration
//! path, which is exactly what `auth::auth_token`'s host check exists to
//! prevent; the same reasoning applies here, so the base is compiled in.
//!
//! This is the same posture as `run_exercise`: a fixed, purpose-built command
//! rather than a general capability, which is what keeps the rule against a
//! general command-exec IPC true.

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use uuid::Uuid;

use crate::auth;
use crate::outbox::{self, OutboxEvent};

/// Where this build syncs to.
///
/// Compiled in rather than configurable. `ATLAS_API_URL` is read at build time
/// so a self-hosted build points at its own server without the shipped app
/// offering a field that could be pointed anywhere.
fn api_base() -> String {
    option_env!("ATLAS_API_URL")
        .unwrap_or("http://localhost:5173")
        .trim_end_matches('/')
        .to_string()
}

/// One drain, capped, so the first sync after a month offline does not hold a
/// four-thousand-request loop open.
const BATCH_LIMIT: usize = 100;

#[derive(Debug, Serialize)]
pub struct Pending {
    pub count: usize,
    #[serde(rename = "signedIn")]
    pub signed_in: bool,
}

/// Queue an event. Called on every completion and every graded run.
#[tauri::command]
pub fn sync_queue(app: AppHandle, kind: String, payload: serde_json::Value) -> Result<String, String> {
    let path = outbox::path_for(&app).map_err(|e| format!("{e:#}"))?;
    let event = OutboxEvent {
        client_event_id: Uuid::new_v4().to_string(),
        kind,
        occurred_at: now_iso(),
        seq: outbox::next_seq(&path),
        payload,
    };
    outbox::append(&path, &event).map_err(|e| format!("{e:#}"))?;
    Ok(event.client_event_id)
}

/// How much is waiting, and whether there is an account to send it to.
#[tauri::command]
pub fn sync_pending(app: AppHandle) -> Result<Pending, String> {
    let path = outbox::path_for(&app).map_err(|e| format!("{e:#}"))?;
    Ok(Pending {
        count: outbox::read_all(&path).len(),
        signed_in: auth::token_for(&app, &api_base()).is_some(),
    })
}

#[derive(Debug, Deserialize)]
struct BatchResponse {
    accepted: usize,
    awarded: i64,
    rejected: Vec<Rejected>,
    game: serde_json::Value,
}

#[derive(Debug, Deserialize)]
struct Rejected {
    #[serde(rename = "clientEventId")]
    client_event_id: String,
    reason: String,
}

#[derive(Debug, Serialize)]
pub struct DrainResult {
    pub status: String,
    pub sent: usize,
    pub accepted: usize,
    pub dropped: usize,
    pub awarded: i64,
    pub remaining: usize,
    pub game: Option<serde_json::Value>,
    pub detail: Option<String>,
}

/// Send what is queued, once.
///
/// The outcome decides what happens to the queue, and getting this wrong in
/// either direction is bad in a different way. Retrying a permanently rejected
/// event forever wedges the queue behind it; dropping one on a network blip
/// loses work. So: accepted and permanently rejected are both forgotten, and
/// everything else is kept for the next attempt.
#[tauri::command]
pub async fn sync_drain(app: AppHandle) -> Result<DrainResult, String> {
    drain(app).await.map_err(|e| format!("{e:#}"))
}

async fn drain(app: AppHandle) -> Result<DrainResult> {
    let base = api_base();
    let path = outbox::path_for(&app)?;
    let queued = outbox::read_all(&path);

    if queued.is_empty() {
        return Ok(DrainResult {
            status: "idle".into(),
            sent: 0,
            accepted: 0,
            dropped: 0,
            awarded: 0,
            remaining: 0,
            game: None,
            detail: None,
        });
    }

    let Some(token) = auth::token_for(&app, &base) else {
        return Ok(DrainResult {
            status: "signed-out".into(),
            sent: 0,
            accepted: 0,
            dropped: 0,
            awarded: 0,
            remaining: queued.len(),
            game: None,
            detail: None,
        });
    };

    let batch: Vec<&OutboxEvent> = queued.iter().take(BATCH_LIMIT).collect();
    let response = reqwest::Client::new()
        .post(format!("{base}/api/sync/batch"))
        .bearer_auth(&token)
        .json(&serde_json::json!({ "events": batch }))
        .send()
        .await
        .context("could not reach the server")?;

    let status = response.status();

    // A revoked or expired token. Say so loudly and stop: a silent 401 that
    // quietly stops the outbox is how someone's progress freezes for a month
    // with nothing anywhere reporting it.
    if status.as_u16() == 401 || status.as_u16() == 403 {
        return Ok(DrainResult {
            status: "unauthorized".into(),
            sent: batch.len(),
            accepted: 0,
            dropped: 0,
            awarded: 0,
            remaining: queued.len(),
            game: None,
            detail: Some("This device is no longer connected to your account.".into()),
        });
    }

    if status.is_server_error() {
        return Err(anyhow!("the server is having trouble ({status})"));
    }

    if !status.is_success() {
        // A 4xx on the whole batch means the request shape is wrong, not that
        // the work was bad. Keep the events; a retry after an update may work.
        return Err(anyhow!("the server refused the batch ({status})"));
    }

    let body: BatchResponse = response.json().await.context("could not read the response")?;

    // Accepted events and permanently rejected ones are both forgotten. A
    // rejection is reported rather than silently swallowed, because "your lesson
    // no longer exists" is something the learner should see once.
    let mut settled: Vec<String> = batch
        .iter()
        .take(body.accepted + body.rejected.len())
        .map(|event| event.client_event_id.clone())
        .collect();
    for rejection in &body.rejected {
        if !settled.contains(&rejection.client_event_id) {
            settled.push(rejection.client_event_id.clone());
        }
    }
    outbox::ack(&path, &settled)?;

    let detail = body
        .rejected
        .first()
        .map(|r| format!("{} event(s) could not be synced: {}", body.rejected.len(), r.reason));

    Ok(DrainResult {
        status: "synced".into(),
        sent: batch.len(),
        accepted: body.accepted,
        dropped: body.rejected.len(),
        awarded: body.awarded,
        remaining: outbox::read_all(&path).len(),
        game: Some(body.game),
        detail,
    })
}

#[derive(Debug, Deserialize, Serialize)]
pub struct PairStart {
    #[serde(rename = "userCode")]
    pub user_code: String,
    #[serde(rename = "verificationUriComplete")]
    pub verification_uri_complete: String,
    #[serde(rename = "intervalSeconds")]
    pub interval_seconds: u64,
    /// Held so the frontend can poll without ever seeing a token.
    #[serde(rename = "deviceCode")]
    pub device_code: String,
}

/// Begin pairing. Returns the code to show and the URL to open.
#[tauri::command]
pub async fn sync_pair_start(name: String, platform: String) -> Result<PairStart, String> {
    let base = api_base();
    let response = reqwest::Client::new()
        .post(format!("{base}/api/devices/start"))
        .json(&serde_json::json!({
            "name": name,
            "platform": platform,
            "appVersion": env!("CARGO_PKG_VERSION"),
        }))
        .send()
        .await
        .map_err(|e| format!("could not reach the server: {e}"))?;

    response
        .json::<PairStart>()
        .await
        .map_err(|e| format!("could not read the response: {e}"))
}

#[derive(Debug, Serialize)]
pub struct PairPoll {
    pub status: String,
    pub account: Option<auth::Account>,
}

/// Poll once for approval, storing the token in Rust if it has arrived.
///
/// The token is written straight to the credential file and is never returned.
/// The frontend learns only that pairing succeeded and who it succeeded as.
#[tauri::command]
pub async fn sync_pair_poll(app: AppHandle, device_code: String) -> Result<PairPoll, String> {
    let base = api_base();
    let response = reqwest::Client::new()
        .post(format!("{base}/api/devices/token"))
        .json(&serde_json::json!({ "deviceCode": device_code }))
        .send()
        .await
        .map_err(|e| format!("could not reach the server: {e}"))?;

    #[derive(Deserialize)]
    struct TokenResponse {
        status: String,
        token: Option<String>,
        email: Option<String>,
        #[serde(rename = "displayName")]
        display_name: Option<String>,
    }

    let body: TokenResponse = response
        .json()
        .await
        .map_err(|e| format!("could not read the response: {e}"))?;

    if body.status != "approved" {
        return Ok(PairPoll {
            status: body.status,
            account: None,
        });
    }

    let (Some(token), Some(email), Some(display_name)) =
        (body.token, body.email, body.display_name)
    else {
        return Err("the server approved the pairing but sent no token".into());
    };

    let account = auth::auth_store(app, token, email, display_name, base)?;
    Ok(PairPoll {
        status: "approved".into(),
        account: Some(account),
    })
}

/// UTC, to the millisecond, which is what the API's schema expects.
fn now_iso() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs() as i64;
    let millis = now.subsec_millis();
    let (year, month, day, hour, minute, second) = civil_from_unix(secs);
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{millis:03}Z")
}

/// Days-from-civil, in reverse. Avoids a date crate for one format string.
fn civil_from_unix(secs: i64) -> (i64, u32, u32, u32, u32, u32) {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);

    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    let year = if m <= 2 { y + 1 } else { y };

    (
        year,
        m,
        d,
        (rem / 3600) as u32,
        ((rem % 3600) / 60) as u32,
        (rem % 60) as u32,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_a_timestamp_the_api_will_accept() {
        // The API parses these with `z.iso.datetime()`, which wants exactly this
        // shape. Getting it wrong would reject every queued event at the schema.
        let stamp = now_iso();
        assert_eq!(stamp.len(), 24, "{stamp}");
        assert!(stamp.ends_with('Z'), "{stamp}");
        assert_eq!(&stamp[4..5], "-");
        assert_eq!(&stamp[10..11], "T");
        assert_eq!(&stamp[19..20], ".");
    }

    #[test]
    fn converts_known_instants() {
        assert_eq!(civil_from_unix(0), (1970, 1, 1, 0, 0, 0));
        // 2026-08-23T09:41:32Z
        assert_eq!(civil_from_unix(1_787_478_092), (2026, 8, 23, 9, 41, 32));
        // A leap day, which is where a hand-rolled calendar goes wrong.
        assert_eq!(civil_from_unix(1_709_164_800), (2024, 2, 29, 0, 0, 0));
        // The day after one, and a year boundary.
        assert_eq!(civil_from_unix(1_709_251_200), (2024, 3, 1, 0, 0, 0));
        assert_eq!(civil_from_unix(1_735_689_599), (2024, 12, 31, 23, 59, 59));
        assert_eq!(civil_from_unix(1_735_689_600), (2025, 1, 1, 0, 0, 0));
    }

    #[test]
    fn the_api_base_has_no_trailing_slash() {
        assert!(!api_base().ends_with('/'));
    }
}
