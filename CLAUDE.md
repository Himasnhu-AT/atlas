# Working in this repo

A code-first learning platform: a Next.js site to read on, a Tauri desktop app to practice in,
and the courses themselves as a versioned package both consume. The first course is AI agent
engineering; the architecture assumes there will be others.

## Layout

```
apps/web/          Next.js 16, App Router. The site and the API for both clients.
apps/desktop/      Tauri 2 + Vite. The three-pane practice IDE.
packages/learning/ The courses: MDX lessons, Python exercises, and the build that validates them.
packages/core/     Domain types, zod schemas, the typed API client.
packages/ui/       Shared React components and the Tailwind v4 theme.
```

## Rules that are easy to break

**Content lives in `packages/learning`, never in app code.** Both apps read the built
manifest. A lesson hard-coded into a component is a bug.

**A course owns its own vocabulary.** `courses/<id>/course.yaml` declares that course's
tracks, and a module's `track` must name one of them. There is no global track enum and there
should never be one again: the old `base | cli | agent | frameworks | projects` was the AI
course's outline promoted to a type, and every later course would have had to either misuse a
word or widen a union nobody else needed. The same goes for `lib/`: a course ships what its
exercises import, and no other course knows about it.

**Nothing crosses a course boundary.** A prerequisite may only name a module in its own
course, and the build refuses one that does not. A course that cannot be started on its own is
a later chapter of another one.

**Run `pnpm content` after touching content.** The apps import `dist/`, which is gitignored,
so a fresh checkout has no lessons until the content build runs. `pnpm dev` does this for you.

**The student's file is always `solution.py`.** `scaffold.py` is copied to that name on first
open and `test.py` imports from it. The fixed name is what lets one test grade both a
student's attempt and the reference, which is what makes the build gate work. Do not
parameterise it.

**Exercises open on the scaffold, never the reference.** Revealing the solution is a
deliberate, confirmed, recorded action. This is pedagogy, not decoration.

**Every exercise runs against `mockllm`, and the platform has no AI in it.** No tutor, no
generated hints, no model calls at runtime. Exercises need no API key and no network.

**Exercises grade in two places and must mean the same thing in both.** The desktop runs a
real interpreter; the web runs CPython on WebAssembly in a worker. Both post to
`/api/attempts`, which decides what the attempt was worth, so nothing about the runner may
affect the reward. Whether an exercise can run in a browser is derived by the content build
from its own imports, never authored, and `packages/learning/src/browser.ts` records what is
unsupported and how that was measured. Do not make it a runtime attempt: `parallel-dispatch`
does not error under the browser runtime, it silently fails 15 of its 24 tests.

**Tailwind v4 only.** `@import "tailwindcss"` plus `@theme` in `packages/ui/src/styles.css`.
There is no `tailwind.config.js` and there never should be.

**Shared packages ship TypeScript source, not a build.** Both apps compile them
(`transpilePackages` in Next, plain workspace resolution in Vite). Relative imports inside
them must not carry `.ts` extensions, because Next rejects those.

**The free/paid boundary is one function.** `apps/web/lib/server/access.ts` decides what a plan
may open, and every surface that could leak content calls it. A boundary spread across route
handlers is a boundary with a hole in it, and the hole is always the newest handler. Free is
each course's first declared track, so the rule is a content decision in `course.yaml` rather
than a list of ids here that goes stale. There is no payment provider: `users.plan` is set by
hand, deliberately, until there is something worth charging for.

The desktop app bundles every lesson so it works offline, so the gate does not reach it. The
place it can be enforced is the content sync, and that is named in `access.ts` rather than
half-built.

## The security boundary

Clients never touch the database. The Supabase service key lives only in
`apps/web/lib/server/` and never reaches a browser or the Tauri bundle. That makes the API the
boundary, not row level security:

**Every route handler derives `user_id` from the session. No handler ever reads a user id from
a request body.** Zod schemas in `packages/core` deliberately omit `userId` so a smuggled one
is dropped at parse time. RLS is enabled in `supabase/schema.sql` as a second layer; nothing
depends on it.

Two more, in the Rust backend:

**`workspace::resolve` guards every filesystem path.** It canonicalizes and rejects anything
escaping the root. Never join a caller-supplied path without it.

**There is no general command-exec IPC.** `run_exercise`, `run_tests` and `project_analyse`
build a command from a fixed interpreter table. Keep it that way.

## Two workspaces, two roots

Exercises live in the app's sandbox under app-data. The app creates it, owns it, and
`SymlinkPolicy::Forbid` applies: nothing in there is written by a human, so any symlink is a
bug or an attack.

A **project** is the student's own repository, so the app reaches outside that sandbox. The
rule that makes it legitimate is explicit consent:

**A project root can only be established through the OS folder picker.** There is deliberately
no `project_open_path(path)` command. One would let anything reaching the IPC bridge read the
disk, which is the whole attack. The user points at a directory; from then on every path
resolves against it through the same guard.

Inside a granted root, `SymlinkPolicy::AllowInternal` applies. Real repositories contain
symlinks as a matter of course, and refusing them all would make the editor useless. It is not
a weaker escape guarantee: the target is canonicalized and must still be contained, so a
symlink pointing outside the granted root is refused exactly as before.

`project_analyse` is static only. It parses, it never executes, and it needs no model. That is
what lets it run on save. Whether an agent is any *good* needs a live model, which stays a
separate, explicit, opt-in step.

## The content build is a gate

`pnpm content` fails on a schema violation, a duplicate id or order, a missing prerequisite, a
prerequisite cycle, a missing exercise file, a broken cross-lesson link, or an exercise whose
reference solution fails its own test. That last check runs the real test against the real
reference in a temp directory.

If you change an exercise, the build tells you whether you broke it. Trust it.

## Writing

Prose in lessons and docs avoids the usual AI tells: no em dashes, sentence case headings, no
emoji, no bold-and-colon list items, no rule-of-three padding, no "let's dive in". Write the
thing rather than announcing it. State tradeoffs plainly instead of selling.

## Checks

```bash
pnpm content        # validate the courses
pnpm typecheck      # TypeScript, every package
pnpm test:core      # the game engine, which is pure and worth over-testing
pnpm test:content   # the content package's own units
pnpm test:rust      # Rust suite
pnpm lint:rust      # clippy, warnings as errors
```

## Reference material

`.tmp-legacy/` holds a third-party curriculum used only to shape the syllabus. It is
gitignored, nothing from it ships, and it can be deleted. Do not import from it.
