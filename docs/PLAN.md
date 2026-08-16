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

Ten modules, two tracks after a shared base, five persona entry points.

```
   5 persona     ┌─ Stage 0 ─ Stage 1 ─ Stage 2 ─┐          (shared base)
   branches ────▶│                               │
                 │        ┌──────────────────────┴──────────────────┐
                 │   Track A, CLI                          Track B, Agent
                 │   A1 → A2 → A3            Stage 3 → 4 → 5 → 6 → 7 → 7.5 → 8
                 └────────────────┬───────────────────────────────────┘
                              CAPSTONE
```

| # | Module | Exercises |
|---|---|---|
| 0 | Foundations. How the course works, setup, first passing test | 1 |
| 1 | LLM fundamentals. Tokens, context, sampling, the completion loop | 3 |
| 2 | Prompt engineering. Structure, few-shot, decomposition, evaluation | 2 |
| 3 | Tool use and building an agent. Schemas, the ReAct loop, error handling | 6 |
| 4 | Agent frameworks. What they abstract, and building one agent twice | 4 |
| 5 | The agent tooling ecosystem. MCP, skills, subagents | 2 |
| 6 | Memory and RAG. Embeddings, chunking, retrieval, long term memory | 5 |
| 7 | Multi-agent and production. Orchestration, evals, observability, deploy | 5 |
| 8 | Advanced agentic patterns. Reflection, planning, context engineering | 3 |
| 9 | Agent interfaces. CLI, chat, background, and embedded agents | 3 |

Two pedagogical rules, both carried over from the reference curriculum because they are sound.

The reference solution is not the starting buffer. Each exercise ships a scaffold with
signatures and docstrings and empty bodies, plus a separate complete solution the student has
to deliberately ask for. Reading a working solution after a real attempt teaches something.
Reading one instead of attempting teaches almost nothing.

Twenty minutes is the timebox. Past that, the app offers the reference. Struggling is useful
and grinding is not.

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

`pnpm --filter @learn/learning build` exits non-zero on a schema violation, a duplicate id or
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
│  ├─ web/                      Next.js 15, App Router, frontend and backend
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

## Build order

1. `packages/learning`: schema, build pipeline, validators, `mockllm`. **Done.**
2. Modules 0 through 2 written end to end as the vertical slice. **In progress.**
3. `packages/core`: types, zod schemas, typed API client.
4. `apps/web`: Next.js auth, API routes, static lesson rendering, dashboard.
5. `apps/desktop`: exercise loading, `run_tests`, preflight, device pairing.
6. Modules 3 through 9 and Track A, once the pipeline is proven.
7. Hardening: rate limits, error states, content update flow, a security review of the PTY surface.

## Working assumptions

All ten modules plus Track A eventually, with 0 through 2 first to prove the pipeline. Prose
written to be read by a person: direct, concrete, no filler. The five persona branches become
an onboarding question that orders the dashboard rather than lessons of their own.
