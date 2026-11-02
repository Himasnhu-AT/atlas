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
    memgate --profile release -- pnpm tauri build --target universal-apple-darwin --bundles app,dmg
)

bundle=apps/desktop/src-tauri/target/universal-apple-darwin/release/bundle
dmg="$(ls -t "$bundle"/dmg/*.dmg | head -1)"
codesign --verify --deep --strict "$bundle/macos/"*.app

echo "Notarizing $(basename "$dmg") (usually a few minutes)"
xcrun notarytool submit "$dmg" --keychain-profile "$profile" --wait --timeout 30m |
  tee /dev/stderr | grep -q "status: Accepted"
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

gh release upload "$tag" "$dmg" --repo "$repo" --clobber

assets="$(gh api "repos/$repo/releases/$release_id" --jq '.assets[].name')"
draft="$(gh api "repos/$repo/releases/$release_id" --jq '.draft')"
if [[ "$draft" == "true" ]] && grep -q '\.msi$' <<<"$assets"; then
  gh release edit "$tag" --repo "$repo" --draft=false --latest
  echo "Published $tag."
elif [[ "$draft" == "true" ]]; then
  echo "Uploaded. CI publishes $tag once the Windows build finishes."
else
  echo "Uploaded to the published release $tag."
fi
