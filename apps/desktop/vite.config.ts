import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Vite config for the Tauri shell.
 *
 * Differences from apps/web that are load-bearing:
 *
 * - port 5174 / strictPort — `tauri.conf.json` points `devUrl` at exactly this
 *   URL, so a silent fallback to 5175 would leave the window on a blank page.
 * - `clearScreen: false` — the Tauri CLI multiplexes cargo output into the same
 *   terminal; wiping the screen would eat Rust compiler errors.
 * - `envPrefix` includes `TAURI_` so `TAURI_ENV_*` is readable from the
 *   frontend alongside the usual `VITE_*` variables.
 * - a fixed `build.target` per platform: the webviews Tauri embeds (WKWebView on
 *   macOS/iOS, WebView2 on Windows, WebKitGTK on Linux) are older than the
 *   browsers `es2022` targets by default.
 */

// The @atlas/* workspace packages are source-only (no build step). Vite must
// compile them from TypeScript source rather than pre-bundling them with
// esbuild, otherwise dependency optimisation caches stale copies and JSX in
// those packages is not transformed by @vitejs/plugin-react.
const workspacePackages = ['@atlas/core', '@atlas/ui', '@atlas/learning']

// Set by `tauri dev --host` when developing against a phone/other machine.
const devHost = process.env['TAURI_DEV_HOST']
const isWindows = process.env['TAURI_ENV_PLATFORM'] === 'windows'
const isDebugBuild = process.env['TAURI_ENV_DEBUG'] === 'true'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  envPrefix: ['VITE_', 'TAURI_'],
  optimizeDeps: {
    exclude: workspacePackages,
  },
  server: {
    port: 5174,
    strictPort: true,
    host: devHost ?? false,
    hmr: devHost ? { protocol: 'ws', host: devHost, port: 5175 } : undefined,
    watch: {
      // Rust build artefacts churn constantly; watching them wedges the dev server.
      ignored: ['**/src-tauri/**'],
    },
  },
  preview: {
    port: 4174,
    strictPort: true,
  },
  build: {
    target: isWindows ? 'chrome105' : 'safari15',
    // `true` keeps Vite's own default minifier — naming one explicitly (e.g.
    // 'esbuild') pulls in a package this workspace does not install.
    minify: !isDebugBuild,
    sourcemap: isDebugBuild,
    emptyOutDir: true,
    // CodeMirror, xterm and the whole course text ship in one chunk that is
    // read off local disk, not downloaded — the web-oriented 500 kB warning is
    // noise here.
    chunkSizeWarningLimit: 2_500,
  },
})
