import 'server-only'

/** Where the desktop installers are published, by .github/workflows/release.yml. */
export const RELEASE_REPO = 'Himasnhu-AT/atlas'
export const RELEASES_URL = `https://github.com/${RELEASE_REPO}/releases`

export interface Installer {
  name: string
  url: string
  size: number
}

export interface DesktopRelease {
  version: string
  url: string
  publishedAt: string
  mac: Installer | null
  windows: Installer | null
}

interface GithubAsset {
  name: string
  browser_download_url: string
  size: number
}

function pick(assets: GithubAsset[], test: (name: string) => boolean): Installer | null {
  const asset = assets.find((a) => test(a.name.toLowerCase()))
  return asset ? { name: asset.name, url: asset.browser_download_url, size: asset.size } : null
}

/**
 * The newest published release, or null when there is none yet or GitHub is
 * unreachable. Cached for ten minutes, which keeps the page well inside
 * GitHub's unauthenticated rate limit however much traffic it gets.
 */
export async function latestDesktopRelease(): Promise<DesktopRelease | null> {
  try {
    const res = await fetch(`https://api.github.com/repos/${RELEASE_REPO}/releases/latest`, {
      headers: { accept: 'application/vnd.github+json' },
      next: { revalidate: 600 },
    })
    if (!res.ok) return null
    const release = (await res.json()) as {
      tag_name: string
      html_url: string
      published_at: string
      assets: GithubAsset[]
    }
    return {
      version: release.tag_name.replace(/^v/, ''),
      url: release.html_url,
      publishedAt: release.published_at,
      mac: pick(release.assets, (n) => n.endsWith('.dmg')),
      // The MSI is the standard Windows installer: it lands in Installed apps and
      // the Start menu. The NSIS setup.exe does the same and is the fallback.
      windows:
        pick(release.assets, (n) => n.endsWith('.msi')) ??
        pick(release.assets, (n) => n.endsWith('-setup.exe')),
    }
  } catch {
    return null
  }
}
