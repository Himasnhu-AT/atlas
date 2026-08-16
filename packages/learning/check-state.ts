import { exerciseState, type ExerciseState } from '../../apps/desktop/src/lib/exerciseState'
type Case = { s: boolean; p?: string; h?: string; want: ExerciseState; why: string }
const CASES: Case[] = [
  { s: false, p: undefined, h: 'a', want: 'fresh', why: 'first ever open' },
  { s: false, p: 'a', h: 'a', want: 'fresh', why: 'stamp survived a deleted solution' },
  { s: false, p: 'a', h: 'b', want: 'fresh', why: 'moved, but nothing of theirs was here' },
  { s: false, p: undefined, h: undefined, want: 'fresh', why: 'no hash, no work' },
  { s: true, p: 'a', h: 'a', want: 'restored', why: 'nothing moved' },
  { s: true, p: 'a', h: 'b', want: 'changed', why: 'THE CASE: rewritten under their work' },
  { s: true, p: undefined, h: 'a', want: 'unknown', why: 'workspace predates stamping' },
  { s: true, p: 'a', h: undefined, want: 'unknown', why: 'build shipped no hash' },
  { s: true, p: undefined, h: undefined, want: 'unknown', why: 'neither side known' },
]
let bad = 0
for (const c of CASES) {
  const got = exerciseState({ hasSolution: c.s, previousStamp: c.p, currentHash: c.h })
  const ok = got === c.want
  if (!ok) bad++
  console.log(`${ok ? 'ok  ' : 'FAIL'} solution=${String(c.s).padEnd(5)} stamp=${(c.p ?? '-').padEnd(3)} hash=${(c.h ?? '-').padEnd(3)} -> ${got.padEnd(8)} ${c.why}`)
}
console.log(`\n${CASES.length - bad}/${CASES.length} correct`)
if (bad) process.exit(1)
