#!/usr/bin/env bash
# Cut a desktop release: ./release.sh 0.2.0
#
# Sets the version everywhere the app reads it, commits, tags v<version> and
# pushes. The tag starts .github/workflows/release.yml, which builds macOS and
# Windows installers and publishes them as a GitHub Release. The site's
# download page picks up the new release within ten minutes.
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
git commit -m "release: $tag"
git tag -a "$tag" -m "Atlas Practice $tag"
git push origin main "$tag"

repo="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo Himasnhu-AT/atlas)"
echo
echo "Pushed $tag. Builds take about 15 minutes:"
echo "  https://github.com/$repo/actions/workflows/release.yml"
