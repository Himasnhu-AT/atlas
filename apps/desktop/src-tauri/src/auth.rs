//! Where the desktop app keeps its API session token.
//!
//! The token is a bearer credential worth thirty days of access to the
//! learner's account, so it is deliberately not kept in the webview's
//! localStorage next to ordinary app state. It lives in a single file in the
//! app-data directory, written `0600` on Unix, and the frontend only ever holds
//! it in memory for the length of a request.
//!
//! This is not a keychain. A keychain is the right long term answer and needs a
//! platform plugin; this is the honest middle step, and it is already a good
//! deal better than a string the page's own JavaScript can read at any time.

use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, Runtime};

/// What the frontend gets back. Never includes the token itself.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Account {
    pub email: String,
    #[serde(rename = "displayName")]
    pub display_name: String,
    /// Where the token is valid. Kept so a change of server invalidates it
    /// rather than silently sending one host's token to another.
    #[serde(rename = "apiBase")]
    pub api_base: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct Stored {
    token: String,
    #[serde(flatten)]
    account: Account,
}

fn credentials_path<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf> {
    let dir = app
        .path()
        .app_data_dir()
        .context("could not determine the application data directory")?;
    fs::create_dir_all(&dir)
        .with_context(|| format!("could not create {}", dir.display()))?;
    Ok(dir.join("credentials.json"))
}

fn read_stored<R: Runtime>(app: &AppHandle<R>) -> Result<Option<Stored>> {
    let path = credentials_path(app)?;
    let raw = match fs::read_to_string(&path) {
        Ok(raw) => raw,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error).context("could not read the stored credentials"),
    };
    // A corrupt file is treated as "not signed in" rather than as an error.
    // The only cost is signing in again, and failing the whole app because one
    // cache file got truncated would be the wrong trade.
    Ok(serde_json::from_str(&raw).ok())
}

fn write_stored(path: &PathBuf, stored: &Stored) -> Result<()> {
    let body = serde_json::to_string_pretty(stored).context("could not encode the credentials")?;
    fs::write(path, body)
        .with_context(|| format!("could not write credentials to {}", path.display()))?;
    restrict(path)
}

/// Owner read/write only. Best effort: a filesystem without Unix modes (a
/// FAT volume, or Windows) simply does not get this, which is why the token is
/// scoped and expiring rather than a password.
fn restrict(path: &PathBuf) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(path)
            .with_context(|| format!("could not stat {}", path.display()))?
            .permissions();
        perms.set_mode(0o600);
        fs::set_permissions(path, perms)
            .with_context(|| format!("could not restrict {}", path.display()))?;
    }
    #[cfg(not(unix))]
    {
        let _ = path;
    }
    Ok(())
}

/// Save a token issued by the API. Replaces whatever was there.
#[tauri::command]
pub fn auth_store(
    app: AppHandle,
    token: String,
    email: String,
    display_name: String,
    api_base: String,
) -> Result<Account, String> {
    let account = Account {
        email,
        display_name,
        api_base,
    };
    let stored = Stored {
        token,
        account: account.clone(),
    };
    let path = credentials_path(&app).map_err(|e| format!("{e:#}"))?;
    write_stored(&path, &stored).map_err(|e| format!("{e:#}"))?;
    Ok(account)
}

/// Replace the stored token, keeping the account it belongs to.
///
/// The server slides the session window: any authenticated request made with a
/// token past the halfway mark of its life comes back carrying a replacement.
/// Storing it is what makes the window mean anything. Without this a device in
/// daily use is signed out on the thirtieth day regardless, and the first the
/// learner hears of it is the outbox refusing to drain.
///
/// Not a `tauri::command`. The token must never be reachable from the webview,
/// and nothing in the frontend has any reason to hand one over.
pub fn replace_token<R: Runtime>(app: &AppHandle<R>, token: &str) -> Result<()> {
    let Some(stored) = read_stored(app)? else {
        // Signed out between the request going out and the reply coming back.
        // Writing the token now would sign them back in behind their back.
        return Ok(());
    };

    let path = credentials_path(app)?;
    write_stored(
        &path,
        &Stored {
            token: token.to_string(),
            account: stored.account,
        },
    )
}

/// Who is signed in, without handing back the token.
#[tauri::command]
pub fn auth_account(app: AppHandle) -> Result<Option<Account>, String> {
    read_stored(&app)
        .map(|stored| stored.map(|s| s.account))
        .map_err(|e| format!("{e:#}"))
}

/// Compare two API bases without tripping over spelling.
///
/// A scheme and host are case-insensitive and a trailing slash means nothing, so
/// `https://Learn.Example.com/` and `https://learn.example.com` are the same
/// server. Comparing the raw strings makes them different, and the failure is
/// silent and total: the token is never released, the app reports "not signed
/// in" forever, and nothing anywhere logs why.
pub fn normalize_api_base(base: &str) -> String {
    base.trim().trim_end_matches('/').to_ascii_lowercase()
}

/// The bearer token, for the frontend to put on one request.
///
/// `api_base` must match the host the token was issued for. Without that check
/// a learner who pointed the app at a different server would send their real
/// token to it on the first sync.
#[tauri::command]
pub fn auth_token(app: AppHandle, api_base: String) -> Result<Option<String>, String> {
    let wanted = normalize_api_base(&api_base);
    let stored = read_stored(&app).map_err(|e| format!("{e:#}"))?;
    Ok(stored.and_then(|s| (normalize_api_base(&s.account.api_base) == wanted).then_some(s.token)))
}

/// The token for a base, for Rust-side callers that already hold an `AppHandle`.
pub fn token_for<R: Runtime>(app: &AppHandle<R>, api_base: &str) -> Option<String> {
    let wanted = normalize_api_base(api_base);
    read_stored(app)
        .ok()
        .flatten()
        .and_then(|s| (normalize_api_base(&s.account.api_base) == wanted).then_some(s.token))
}

/// Sign out: remove the file entirely rather than blanking it.
#[tauri::command]
pub fn auth_clear(app: AppHandle) -> Result<(), String> {
    let path = credentials_path(&app).map_err(|e| format!("{e:#}"))?;
    match fs::remove_file(&path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(format!("could not sign out: {error}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn sample() -> Stored {
        Stored {
            token: "tok-abc".into(),
            account: Account {
                email: "reader@example.com".into(),
                display_name: "Reader".into(),
                api_base: "https://learn.example.com".into(),
            },
        }
    }

    // The command wrappers need an AppHandle, so these cover the file layer
    // underneath them, which is where the interesting behaviour is.

    #[test]
    fn round_trips_through_the_file() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("credentials.json");
        write_stored(&path, &sample()).unwrap();

        let raw = fs::read_to_string(&path).unwrap();
        let back: Stored = serde_json::from_str(&raw).unwrap();
        assert_eq!(back.token, "tok-abc");
        assert_eq!(back.account.email, "reader@example.com");
    }

    #[test]
    fn replacing_a_token_keeps_the_account() {
        // The refresh path must not quietly change who is signed in, and must
        // not resurrect a session somebody just signed out of.
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("credentials.json");

        let stored = sample();
        write_stored(&path, &stored).unwrap();

        let replaced = Stored {
            token: "a-fresher-token".into(),
            account: stored.account.clone(),
        };
        write_stored(&path, &replaced).unwrap();

        let read: Stored = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(read.token, "a-fresher-token");
        assert_eq!(read.account.email, stored.account.email);
        assert_eq!(read.account.api_base, stored.account.api_base);
    }

    #[cfg(unix)]
    #[test]
    fn the_file_is_owner_only() {
        use std::os::unix::fs::PermissionsExt;
        let dir = tempdir().unwrap();
        let path = dir.path().join("credentials.json");
        write_stored(&path, &sample()).unwrap();

        let mode = fs::metadata(&path).unwrap().permissions().mode();
        assert_eq!(
            mode & 0o777,
            0o600,
            "a bearer token must not be group or world readable"
        );
    }

    #[test]
    fn overwriting_keeps_the_restriction() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("credentials.json");
        write_stored(&path, &sample()).unwrap();
        write_stored(&path, &sample()).unwrap();

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = fs::metadata(&path).unwrap().permissions().mode();
            assert_eq!(mode & 0o777, 0o600);
        }
    }

    #[test]
    fn an_api_base_matches_despite_spelling() {
        // A trailing slash or a capital letter used to mean the token was never
        // released and the app reported "not signed in" forever, with nothing
        // anywhere saying why.
        let canonical = normalize_api_base("https://learn.example.com");
        for spelling in [
            "https://learn.example.com/",
            "https://Learn.Example.com",
            "  https://learn.example.com  ",
            "https://learn.example.com///",
        ] {
            assert_eq!(normalize_api_base(spelling), canonical, "{spelling}");
        }
    }

    #[test]
    fn a_different_host_does_not_match() {
        assert_ne!(
            normalize_api_base("https://learn.example.com"),
            normalize_api_base("https://evil.example.com"),
        );
    }

    #[test]
    fn a_corrupt_file_parses_as_nothing() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("credentials.json");
        fs::write(&path, "{not json").unwrap();

        let raw = fs::read_to_string(&path).unwrap();
        assert!(serde_json::from_str::<Stored>(&raw).is_err());
    }
}
