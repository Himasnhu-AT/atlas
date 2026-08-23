/**
 * Copies the browser runtime out of node_modules and into `public/`.
 *
 * Same origin on purpose. A CDN would save the copy and cost the one guarantee
 * the exercises are built around: they run with no network beyond this app, no
 * account with anyone else, and nothing to block. It also keeps the runtime on
 * the same version as the lockfile, so a release cannot silently start grading
 * against a different interpreter than the one the content build was checked on.
 *
 * Only the five files the runtime actually fetches are copied. The package also
 * ships source maps, type definitions and two demo consoles, which together are
 * most of its size on disk and none of its size over the wire.
 */

import { cp, mkdir, stat } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FROM = path.join(HERE, '..', 'node_modules', 'pyodide')
const TO = path.join(HERE, '..', 'public', 'pyodide')

const NEEDED = [
  'pyodide.mjs',
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json',
]

if (!existsSync(FROM)) {
  console.error('pyodide is not installed; run pnpm install')
  process.exit(1)
}

await mkdir(TO, { recursive: true })

let bytes = 0
for (const name of NEEDED) {
  const from = path.join(FROM, name)
  await cp(from, path.join(TO, name))
  bytes += (await stat(from)).size
}

console.log(`Copied the browser runtime, ${(bytes / 1024 / 1024).toFixed(1)} MB.`)
