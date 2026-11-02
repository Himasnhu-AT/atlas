#!/usr/bin/env bash
# Cut a desktop release: ./release.sh 0.2.0
#
# Sets the version everywhere the app reads it, commits, tags v<version> and
# pushes. The tag starts .github/workflows/release.yml, which builds the
# Windows installers on GitHub Actions. Then scripts/release-macos.sh builds,
# signs and notarizes the macOS app on this Mac and uploads it to the same
# release. The site's download page picks it up within ten minutes.
set -euo pipefail

cd "$(dirname "$0")"

version="${1:-}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: ./release.sh <major.minor.patch>   (current: $(node -p "require('./apps/desktop/src-tauri/tauri.conf.json').version"))" >&2
  exit 1
fi
tag="v$version"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "working tree is not clean; commit or stash first" >&2
  exit 1
fi
if [[ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]]; then
  echo "releases are cut from main" >&2
  exit 1
fi
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
  echo "tag $tag already exists" >&2
  exit 1
fi

git pull --ff-only

# The content build is the gate: refuse to tag something that would not build.
pnpm content:check

node - "$version" <<'JS'
const fs = require('fs')
const version = process.argv[2]
for (const file of ['apps/desktop/src-tauri/tauri.conf.json', 'apps/desktop/package.json']) {
  const json = JSON.parse(fs.readFileSync(file, 'utf8'))
  json.version = version
  fs.writeFileSync(file, JSON.stringify(json, null, 2) + '\n')
}
const cargo = 'apps/desktop/src-tauri/Cargo.toml'
fs.writeFileSync(
  cargo,
  fs.readFileSync(cargo, 'utf8').replace(/^version = ".*"$/m, `version = "${version}"`),
)
JS

# Refresh Cargo.lock's entry for the app without touching anything else.
(cd apps/desktop/src-tauri && cargo update --workspace --offline >/dev/null 2>&1 || cargo update --workspace >/dev/null)

git add apps/desktop/src-tauri/tauri.conf.json apps/desktop/package.json \
  apps/desktop/src-tauri/Cargo.toml apps/desktop/src-tauri/Cargo.lock
git diff --cached --quiet || git commit -m "release: $tag"
git tag -a "$tag" -m "Atlas Practice $tag"
git push origin main "$tag"

echo
echo "Pushed $tag. GitHub Actions is building Windows:"
echo "  https://github.com/Himasnhu-AT/atlas/actions/workflows/release.yml"
echo "Building, signing and notarizing macOS here."
echo

# If this fails, fix it and rerun `scripts/release-macos.sh $tag`; the release
# stays a draft until the notarized dmg is on it.
scripts/release-macos.sh "$tag"
