# Build plan

Decisions are settled. Implementation is under way.

## Decisions

| # | Decision |
|---|---|
| D1 | Content is original, written from scratch. `.tmp-legacy/` is reference for syllabus shape only. None of its prose or code ships, so there is nothing to attribute. |
| D2 | Lessons are MDX. Frontmatter declares the module, the exercise, and the exercise's files. |
| D3 | Grading is deterministic and offline: a Python test file driving a scripted model client. |
| D4 | English only. No locale tree. |
| D5 | Preflight checks the Python toolchain and degrades gracefully. It never hard fails. |
| D6 | Content ships bundled in both apps. An API tracks versions and pushes updates. |
| D7 | The client never sees Supabase. Everything goes through the Next.js backend. |
| D8 | Students only. No teacher, classroom, cohort, or organization concepts. |
| D9 | Supabase stores users, progress, and a module registry. No content bodies. |
| D10 | The platform contains no AI features. No tutor, no generated hints, no chat. |
| D11 | Exercises need no model. Students write agent code against a mock client we ship. |

### What D10 and D11 buy

The app works on a plane, on a locked down laptop, with nothing installed but Python 3.10 or
newer. Tests run in about a second and give the same answer every time, so a red test is
always the student's bug. Nobody hits a paywall, a rate limit, or a two gigabyte model
download before finishing lesson one. There are no API keys anywhere in the system and no
inference cost.

The tradeoff is real. Students never watch a live model surprise them, and that is a genuine
part of the craft. It is what the provider modules exist for later. For now the loop is the
thing being taught, and the loop is what the tests check.

## Syllabus

Two courses now, not one, and `docs/CURRICULUM.md` is the authority on both. It
carries the spine, the threads, the module maps and the rules about measured
rather than aspirational hours. This file used to hold a ten module list with
persona branches and a CLI track; none of that survived contact with the
writing, and keeping a second copy of a syllabus only produces two that
disagree.

Two pedagogical rules from that work belong here, because they constrain the
build rather than the prose.

The reference solution is not the starting buffer. Each exercise ships a scaffold
with signatures and docstrings and empty bodies, plus a separate complete
solution the student has to deliberately ask for. Reading a working solution
after a real attempt teaches something. Reading one instead of attempting
teaches almost nothing.

The timebox is per exercise and declared in frontmatter. Past it, the app offers
the reference. Struggling is useful and grinding is not.

## The content package

```
packages/learning/
├─ modules/
│  └─ 00-foundations/
│     ├─ module.yaml                    id, version, track, prerequisites
│     ├─ 01-how-this-course-works.mdx
│     ├─ 02-check-your-setup.mdx
│     └─ exercises/
│        └─ check-your-setup/
│           ├─ scaffold.py              the student's starting buffer
│           ├─ reference.py             complete worked solution
│           └─ test.py                  the grader
├─ lib/mockllm.py                       scripted model client, stdlib only
├─ scripts/build.ts                     parse, validate, compile, emit
└─ dist/                                gitignored
   ├─ manifest.json                     module and lesson tree, versions
   └─ lessons/<id>.json                 compiled MDX plus exercise files
```

`mockllm.py` is copied into every exercise workspace by the build rather than installed. A
student needs nothing but a Python interpreter to run their first test.

The student's working file is always `solution.py`. `scaffold.py` is copied to that name when
the exercise first opens, and `test.py` imports from it. Because the name is fixed, one test
file grades both the student's attempt and the reference solution.

### The build is a gate

`pnpm --filter @atlas/learning build` exits non-zero on a schema violation, a duplicate id or
order, a prerequisite naming a module that does not exist, a prerequisite cycle, a lesson
declaring an exercise whose files are missing, a cross-lesson link pointing nowhere, or an
exercise whose reference solution fails its own test.

That last check is the point. It runs the real test against the real reference in a throwaway
directory, so a broken exercise cannot ship. Verified working: breaking a reference on purpose
fails the build with the exact assertion diff.

### How modules load

| Consumer | Mechanism |
|---|---|
| Authoring | Edit MDX. The watch mode revalidates on save. |
| Next.js web | Imports `manifest.json` at build time and statically generates every lesson page. Rendering content costs zero database reads. |
| Tauri desktop | Manifest, lessons, and exercises are bundled as Tauri resources, so the app works offline on first launch. On startup it calls `/api/content/manifest` and pulls only the modules whose version moved. |

## Supabase

Content bodies never reach the database. `modules` is a registry, not content: it tells the
backend what is live, at what version, and what unlocks what.

```
users                 id · email · display_name · avatar_url · created_at · last_seen_at

modules               id · slug · name
                      version             drives the desktop update check
                      is_active           hide a module without a deploy
                      prerequisites       module ids
                      track · order · difficulty · estimated_hours · updated_at

module_progress       user_id · module_id · status · lessons_completed · lessons_total
                      started_at · completed_at          PK (user_id, module_id)

lesson_progress       user_id · module_id · lesson_id · status · seconds_spent
                      started_at · completed_at          PK (user_id, lesson_id)

exercise_state        user_id · exercise_id · current_code
                      peeked_reference_at · updated_at   PK (user_id, exercise_id)

exercise_attempts     id · user_id · exercise_id · passed · tests_passed · tests_total
                      stdout_tail · duration_ms · created_at        append only

devices               id · user_id · name · platform · app_version
                      created_at · last_seen_at · revoked_at        desktop pairing

activity_days         user_id · day · lessons_touched · attempts    streaks
```

`lesson_progress.lesson_id` stays plain text. Lessons live in the bundle, and the API
validates the id against the manifest before writing, so there are no orphan rows.

Nothing else is stored: not lesson bodies, not the student's workspace files, not API keys
(there are none), and not test execution. We record the verdict and never run student code
on a server.

### What D7 changes

Because the client never sees Supabase, RLS stops being the security boundary. The Next.js API
is.

Supabase is used as Postgres only, reached server side with the service role key. That key
lives in the Next.js server environment and never reaches a browser or the Tauri bundle. Auth
is issued by Next.js: httpOnly cookie sessions on web, and a paired refresh token on desktop.
Every route handler resolves the session and derives `user_id` server side, and none of them
trust a `user_id` from a request body. That rule is what replaces RLS. RLS is switched on
anyway as a second layer, but nothing depends on it.

## Repo layout

```
learn/
├─ apps/
│  ├─ web/                      Next.js 16, App Router, frontend and backend
│  │  ├─ app/
│  │  │  ├─ (marketing)/        landing, download
│  │  │  ├─ (auth)/             login, signup, callback
│  │  │  ├─ (learn)/            dashboard, tracks, learn/[module]/[lesson]
│  │  │  └─ api/                content, progress, attempts, auth/device
│  │  ├─ lib/server/            the only place holding the Supabase service key
│  │  └─ middleware.ts          session refresh and route guards
│  └─ desktop/                  Tauri v2, Vite and React, talks to /api
│     ├─ src/                   three panes: lesson, editor, terminal
│     └─ src-tauri/             Rust: PTY, sandboxed workspace, preflight, test runner
├─ packages/
│  ├─ learning/                 content and build pipeline
│  ├─ ui/                       shared components and Tailwind theme
│  └─ core/                     domain types, zod schemas, typed API client
└─ docs/
```

Tauri serves static assets with no Node runtime, so server components and route handlers
cannot run inside it. That is why the desktop app is Vite rather than Next.js. The two apps
share packages, not an app shell, which suits them anyway: a three pane IDE is a different
interface from a web reader.

## Preflight

Runs on desktop launch and before any exercise run. Never fatal.

| Check | On failure |
|---|---|
| `python3` on PATH, 3.10 or newer | Banner with install steps for the platform. Reading still works. Run is disabled with a stated reason. |
| Exercise files present in the workspace | Re-materialize them from the bundle. |
| `mockllm.py` importable | Re-copy it from the bundle. |

The list is short by design. D11 removed Ollama, model downloads, virtual environments, and
API keys from v1 entirely. Python 3.10 is the only hard requirement.

## The game

Atlas is a game as well as a course, and the mechanics are cloned honestly from
the interactive-RPG format while the skin deliberately is not. There is no neon
and no pixel art. Rank is a stamp, an achievement is a seal, progress is a rule
drawn partway, and a level-up is the page ruling a line. DESIGN.md holds that
rule; this section holds the logic behind it.

### The economy is derived, never authored

Weights come from `estimatedMinutes`, `timeboxMinutes` and a module's
`difficulty`, all of which already exist in the manifest and are already
measured. Nothing new enters lesson frontmatter, so the content gate is
untouched and the economy cannot drift from the course. Adding a course prices
itself.

| Event | XP |
|---|---|
| Lesson finished | 5, flat |
| Exercise passed | `timeboxMinutes x 2 x difficulty` (x1.0 / x1.25 / x1.5) |
| — no reference revealed | +25% |
| — passed on the first run | +15% |
| Module finished | `100 x difficulty` |
| Quest claimed | 40 daily, 150 weekly |
| Seal earned | 25 to 500, per seal |

Reading pays flat and small on purpose. Paying by length started here and was
wrong: "mark complete" is self-reported and takes one click, so a sixty minute
lesson was worth sixty xp to anyone willing to click through it, and a third of
the economy sat behind a button that verifies nothing. Flat keeps the
acknowledgement and keeps the lessons that carry no exercise worth something,
while the weight moves to work that is actually graded. Exercises are now about
85% of the economy.

Levels use `10(L-1)^2 + 30(L-1)`, which gives 23 levels across a course-sized
body of work: an early level costs about one exercise and a late one about six.
The obvious steeper curve was tried and rejected because it made the last levels
cost more than a whole module, so the back third of a course delivered almost no
level-ups, which is exactly where a learner most needs one. Ranks are eight
tiers of three levels, Wanderer through Magister, named for the atlas rather
than for any one domain.

### Award keys are the whole idempotency story

An award key is a function of the user, the kind, and a natural key for the
thing rewarded. Never a client-supplied id, never a timestamp, never anything
mutable. `unique (user_id, award_key)` and `insert ... on conflict do nothing`
do the rest.

The trap worth naming, because it looks right and passes every test where
somebody completes once: `lesson:<id>:<completedAt>` double-pays on the third
toggle, because `/api/progress` preserves `completedAt` on re-complete and
clears it on un-complete, so the next complete mints a fresh timestamp.

Award keys dedupe xp. They do not dedupe history, and the attempt counters are
what the first-run bonus and two seals read, so the sync batch carries a
`clientEventId` and `unique (user_id, client_event_id)` stops a retried drain
counting a failure twice.

### Quests, seals, and the week

Quests are deterministic: the day's three come from a pool by `hash(userId +
date)`, and their progress is computed from rows the API already writes. No
scheduler, and nothing stored until a claim, which is just an award row. Two
accounts on the same day are offered different quests, which is the intended
behaviour and worth knowing before debugging a claim that pays zero.

Seals are wax stamps for real feats, each a pure predicate over a checked data
source so none can silently never fire. Fourteen of them, from First light to A
year, including Polymath for clearing a module in two different courses.

There is no daily streak. A weekly target the learner sets themselves replaced
it, because a daily streak turns one bad day into a quit and punishes anyone
studying two things at once. The target is a floor they chose, not a ceiling the
product imposed, and days past it are still drawn.

### The user flow

A signed-out reader browses the site and reads the free track. Signing up costs
an email and a password, and level 1 is 0 xp.

The loop is: read a lesson on the web, open its exercise in the desktop app,
write `solution.py` against a scripted model client, run the tests locally, and
watch the ledger move. Marking a lesson complete stamps a small `+5` in the
margin. Passing an exercise pays the bulk of the economy. Crossing a level draws
a rule across the column and presses a rank into the page, once, and then lets it
go.

`/atlas` is the map: courses as regions, and within a region the prerequisite
DAG drawn as a chart, which is the only screen that can show the frameworks
branch is a side road nothing depends on. `/ledger` is the character sheet: rank,
xp, the week, today's quests, and every seal earned or still blank.

Grading happens only on the desktop, so the most xp-worthy event in the product
happens on the machine least able to report it. The desktop queues domain events
rather than xp, in an append-only file beside its credentials, and drains them in
order when it can reach the API. Signed out it shows a practice ledger that is
deliberately not xp ("14 exercises passed, 6 hours of practice"), and that
backlog is the outbox, so somebody who worked offline for three weeks and then
signed up is paid for all of it.

### Assets

Inline SVG, hand-drawn in `packages/ui/src/game/`, using `currentColor` and `em`
sizing so they inherit the theme and print. No image files, no icon font, no new
fonts. An asset that cannot take the ink colour would be the one thing on the
page not made of ink.

They are exported from `@atlas/ui/game` rather than the package barrel, because
the barrel reaches components that use hooks and importing it from a server
component drags `useState` in behind them.

### The honest threat model

Grading is client-side and must stay that way, per D3 and D11: offline, no key,
no network. So a determined person can post a pass for every exercise in the
catalogue. Worse, the app deliberately writes `reference.py` into the workspace,
so copying the reference and passing is a supported action rather than an
exploit. Pretending otherwise would be theatre.

**The distracted student** double-clicks Run or toggles a lesson twice, and must
never be double-paid. Award keys handle this, and it is almost all of the volume.

**The self-cheater** pastes the reference. Deliberately not prevented. The course
is voluntary, there is no credential at the end, and the only person harmed is
them. Similarity scoring produces false accusations against people who genuinely
wrote the same solution, and the model-based version would violate D10.

**The leaderboard griefer** is the only one worth engineering against, and only
because a public board makes cheating visible and demoralising. Five defences, in
value order: a per-day cap on what one day contributes to a board score, award
keys giving the catalogue a finite ceiling, an account-age floor on joining,
weekly scoring on when xp was received rather than earned, and a manual
exclusion flag. No automated banning: `stdout_tail` is recorded and a human
settles a case in a minute.

Explicitly not attempted: grader attestation, signed test reports, proof of work,
obfuscation. Every one is defeated by a user with a debugger on their own
machine, and this platform teaches people to use debuggers.

## Build order

Everything below has shipped. The order is kept because it records what had to
be true before the next thing could start.

1. `packages/learning`: schema, build pipeline, validators, `mockllm`.
2. Modules 0 through 2 end to end, as the vertical slice that proved the pipeline.
3. `packages/core`: types, zod schemas, typed API client.
4. `apps/web`: auth, API routes, lesson rendering, dashboard.
5. `apps/desktop`: exercise loading, `run_tests`, preflight.
6. The rest of the AI course.
7. Courses above modules, so the AI course stopped being the product. Ids gained
   a course prefix, `track` stopped being a global enum, and the gate learned to
   check uniqueness across courses.
8. Five latent bugs fixed before xp was built on them, the worst being that
   `/api/attempts` validated nothing.
9. The rename to Atlas.
10. The game: pure domain layer first, then the ledger, then the routes, then the
    surfaces.
11. Desktop pairing by device authorization grant, device-scoped tokens, and the
    outbox.
12. The data engineering course, which is what proved the course-scoped `lib/`
    mechanism was real rather than theoretical.
13. The membership gate.

## Working assumptions

Prose written to be read by a person: direct, concrete, no filler.
`docs/CURRICULUM.md` holds the rules it is held to.

There is no payment provider. `users.plan` is set by hand, and the gate is
enforced server-side because that is where the boundary is. Free covers each
course's first track, so every course has a real free start.

What is deliberately not built: a tutor, generated hints, or any model call at
runtime (D10); a teacher, classroom or cohort (D8); a general command-exec IPC in
the desktop; and any automated response to suspected cheating.
