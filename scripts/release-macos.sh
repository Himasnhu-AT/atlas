#!/usr/bin/env bash
# Build, sign, notarize and upload the macOS app for a release tag.
#
#   scripts/release-macos.sh v0.2.0
#
# Runs on a Mac because it needs the Developer ID certificate in the login
# keychain and a notarytool keychain profile (NOTARY_PROFILE, default
# "xcnotarize"). ./release.sh calls it after pushing the tag; run it by hand to
# redo the macOS build of an existing release.
#
# CI builds Windows into the same draft release. Whichever of the two finishes
# second publishes it, so a release never goes out without the notarized dmg.
set -euo pipefail

cd "$(dirname "$0")/.."

tag="${1:?usage: scripts/release-macos.sh <tag>}"
profile="${NOTARY_PROFILE:-xcnotarize}"
repo="Himasnhu-AT/atlas"

identity="${APPLE_SIGNING_IDENTITY:-$(security find-identity -v -p codesigning |
  sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/\1/p' | head -1)}"
if [[ -z "$identity" ]]; then
  echo "no Developer ID Application certificate in the keychain" >&2
  exit 1
fi
xcrun notarytool history --keychain-profile "$profile" >/dev/null ||
  { echo "notarytool profile '$profile' does not work" >&2; exit 1; }

# Signs the update archive. Installed apps refuse an update that does not
# verify against the public key in tauri.conf.json, so losing this key means
# shipping a new public key and asking everyone to reinstall by hand.
updater_key="${TAURI_UPDATER_KEY:-$HOME/.tauri/atlas-updater.key}"
[[ -f "$updater_key" ]] || { echo "updater signing key not found at $updater_key" >&2; exit 1; }
updater_password="$(security find-generic-password -s atlas-tauri-updater -w)" ||
  { echo "updater key password not in the keychain (service atlas-tauri-updater)" >&2; exit 1; }

if [[ "$(git rev-parse HEAD)" != "$(git rev-parse "$tag^{commit}")" ]]; then
  echo "HEAD is not $tag; check it out first" >&2
  exit 1
fi

echo "Signing as: $identity"
pnpm content
(
  cd apps/desktop
  APPLE_SIGNING_IDENTITY="$identity" \
  ATLAS_API_URL=https://atlas.himanshuat.com \
  TAURI_SIGNING_PRIVATE_KEY="$(cat "$updater_key")" \
  TAURI_SIGNING_PRIVATE_KEY_PASSWORD="$updater_password" \
    memgate --profile release -- pnpm tauri build --target universal-apple-darwin --bundles app,dmg \
      --config src-tauri/tauri.release.conf.json
)
unset updater_password

bundle=apps/desktop/src-tauri/target/universal-apple-darwin/release/bundle
dmg="$(ls -t "$bundle"/dmg/*.dmg | head -1)"
codesign --verify --deep --strict "$bundle/macos/"*.app

echo "Notarizing $(basename "$dmg") (usually a few minutes)"
# Captured, not piped into `grep -q`: grep exits on the first match, the writer
# then dies of SIGPIPE, and pipefail turns an accepted submission into a failure.
result="$(xcrun notarytool submit "$dmg" --keychain-profile "$profile" --wait --timeout 30m)"
echo "$result"
if ! grep -q "status: Accepted" <<<"$result"; then
  id="$(sed -n 's/^ *id: //p' <<<"$result" | head -1)"
  echo "notarization was not accepted; see: xcrun notarytool log $id --keychain-profile $profile" >&2
  exit 1
fi
xcrun stapler staple "$dmg"
spctl --assess --type open --context context:primary-signature -v "$dmg"

# CI creates the draft release when the tag is pushed. Wait for it.
release_id=""
for _ in $(seq 1 60); do
  release_id="$(gh api "repos/$repo/releases" --jq ".[] | select(.tag_name == \"$tag\") | .id" | head -1)"
  [[ -n "$release_id" ]] && break
  sleep 10
done
[[ -n "$release_id" ]] || { echo "no release for $tag on GitHub" >&2; exit 1; }

version="${tag#v}"
archive="$bundle/macos/Atlas Practice.app.tar.gz"
[[ -f "$archive" && -f "$archive.sig" ]] || { echo "updater archive or signature missing" >&2; exit 1; }
# GitHub turns spaces in asset names into dots; name it so the URL is known.
asset="Atlas.Practice_${version}_universal.app.tar.gz"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp "$archive" "$staging/$asset"

# latest.json is what installed apps poll. CI writes the Windows entries into
# the same file, so merge with whatever is already on the release.
if ! gh release download "$tag" --repo "$repo" --pattern latest.json --dir "$staging" 2>/dev/null; then
  echo '{}' > "$staging/latest.json"
fi
node - "$staging/latest.json" "$version" "$(cat "$archive.sig")" \
  "https://github.com/$repo/releases/download/$tag/$asset" <<'JS'
const fs = require('fs')
const [file, version, signature, url] = process.argv.slice(2)
const manifest = JSON.parse(fs.readFileSync(file, 'utf8'))
manifest.version = version
manifest.pub_date ??= new Date().toISOString()
manifest.notes ??= `Atlas Practice ${version}`
manifest.platforms ??= {}
// One universal build serves both architectures.
for (const platform of ['darwin-aarch64', 'darwin-x86_64']) {
  manifest.platforms[platform] = { signature, url }
}
fs.writeFileSync(file, JSON.stringify(manifest, null, 2) + '\n')
JS

gh release upload "$tag" "$dmg" "$staging/$asset" "$staging/latest.json" --repo "$repo" --clobber

# Publish only once the update manifest names both systems. Whichever side
# finishes second gets here with everything in place; if the two ever wrote
# latest.json at the same moment and one lost, the release stays a draft
# rather than going out with a broken update feed.
manifest_platforms() {
  local id
  id="$(gh api "repos/$repo/releases/$release_id" --jq '.assets[] | select(.name == "latest.json") | .id')"
  [[ -n "$id" ]] || return 0
  gh api -H "Accept: application/octet-stream" "repos/$repo/releases/assets/$id" |
    node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(Object.keys(JSON.parse(s).platforms||{}).join("\n")))'
}
platforms="$(manifest_platforms)"
draft="$(gh api "repos/$repo/releases/$release_id" --jq '.draft')"
if [[ "$draft" != "true" ]]; then
  echo "Uploaded to the published release $tag."
elif grep -q '^darwin-aarch64$' <<<"$platforms" && grep -q '^windows-x86_64' <<<"$platforms"; then
  gh api -X PATCH "repos/$repo/releases/$release_id" -F draft=false -f make_latest=true >/dev/null
  echo "Published $tag."
else
  echo "Uploaded. CI publishes $tag once the Windows build has added itself to latest.json."
fi
