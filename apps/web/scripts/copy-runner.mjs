/**
 * Copies the shared test runner into `public/`, where the grader worker fetches
 * it at boot.
 *
 * `packages/learning/runner/atlas_report.py` is the one file both graders use:
 * the desktop compiles it into the Rust binary with `include_str!`, and the
 * browser fetches this copy. Copying rather than importing because a worker in
 * `public/` is outside the bundler by design, and the alternative is a second
 * copy of the file that drifts from the first.
 *
 * The copy is generated, so it is gitignored and rebuilt on every predev and
 * prebuild alongside the interpreter.
 */

import { copyFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FROM = path.join(HERE, '..', '..', '..', 'packages', 'learning', 'runner', 'atlas_report.py')
const TO = path.join(HERE, '..', 'public', 'atlas_report.py')

if (!existsSync(FROM)) {
  console.error(`copy-runner: no runner at ${FROM}`)
  process.exit(1)
}

await mkdir(path.dirname(TO), { recursive: true })
await copyFile(FROM, TO)
console.log(`copy-runner: atlas_report.py -> ${path.relative(process.cwd(), TO)}`)
