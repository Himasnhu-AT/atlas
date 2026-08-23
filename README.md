# Atlas

A code-first learning platform, and the courses it teaches. Students read lessons on the web
and practice in a desktop app that puts the lesson, a code editor, and a real terminal side by
side. Every exercise is graded locally by tests that run in about a second.

A course is the unit a student picks up. Each one declares its own tracks and ships its own
support library, so a curriculum on data engineering does not have to describe itself in the
vocabulary of one on AI agents. The first course is AI agent engineering.

Nothing in the platform calls a language model. The AI course runs against `mockllm`, a
scripted client with the same shape as a provider SDK, so the loops students write are the
loops they would write against a live provider. There is no API key, no model download, and
no network requirement anywhere.

## Quick start

```bash
pnpm install
pnpm dev            # http://localhost:5173
```

That is the whole setup. The site runs with no configuration: accounts and progress go to a
JSON file under `apps/web/.data/`, and a session key is generated on first run. See
[Going to production](#going-to-production) when you want a real database.

To run the desktop app:

```bash
pnpm dev:desktop    # needs Rust; Python 3.10+ to run exercises
```

## What is here

```
learn/
├─ apps/
│  ├─ web/                  Next.js 16. The site AND the API both clients use.
│  │  ├─ app/(marketing)/   landing, download
│  │  ├─ app/(auth)/        login, signup
│  │  ├─ app/(learn)/       dashboard, curriculum, lesson reader
│  │  ├─ app/api/           progress, attempts, content manifest, auth
│  │  └─ lib/server/        the only code that touches storage or sessions
│  └─ desktop/              Tauri 2. The practice IDE.
│     ├─ src/               three panes: lesson │ editor │ terminal
│     └─ src-tauri/         Rust: PTY, sandboxed workspace, test runner, preflight
└─ packages/
   ├─ learning/             the course itself, plus the build that validates it
   ├─ core/                 domain types, zod schemas, the typed API client
   └─ ui/                   shared React components and the Tailwind theme
```

The desktop app is Vite rather than Next.js because Tauri serves static assets with no Node
runtime, so server components and route handlers cannot run inside it. The two apps share
packages, not an app shell, which suits them: a three-pane IDE is a different interface from
a web reader.

## The courses

Two, and the platform assumes there will be more.

| Course | Modules | Lessons | Exercises | Hours | Needs |
|---|---|---|---|---|---|
| AI agent engineering | 11 | 45 | 35 | 47 | Python 3.10+ |
| Data engineering | 5 | 17 | 13 | 14 | Python 3.10+ |

Neither needs anything installed beyond an interpreter. The AI course runs against `mockllm`;
the data course uses `csv`, `json`, `sqlite3` and `datetime`, all standard library, and ships
its own deterministic fixture generator the same way.

### AI agent engineering

11 modules, 45 lessons and 35 graded exercises, across four tracks.

| # | Module | Track | Lessons | Exercises | Hours |
|---|---|---|---|---|---|
| 0 | Foundations | base | 3 | 2 | 1.5 |
| 1 | LLM fundamentals | base | 4 | 3 | 3.5 |
| 2 | Prompt engineering | base | 4 | 3 | 3.5 |
| 3 | Tool use and building an agent | agent | 5 | 4 | 5.5 |
| 4 | Agent frameworks | agent | 4 | 3 | 4 |
| 5 | Memory and RAG | agent | 5 | 4 | 5.5 |
| 6 | Multi-agent systems and production | agent | 4 | 4 | 5 |
| 7 | State graphs and durable execution | frameworks | 4 | 3 | 4.5 |
| 8 | Handoffs, guardrails, and typed output | frameworks | 4 | 3 | 4 |
| 9 | Support triage that knows when to escalate | projects | 4 | 3 | 5 |
| 10 | Research briefing with verified citations | projects | 4 | 3 | 5 |
| | | | **45** | **35** | **47** |

The hours are measured rather than estimated: each is the module's lesson minutes plus its
exercise timeboxes, so the column adds up to how long the course actually takes if you do the
work.

Students write a sampler, a context budget, a tool-calling loop, a ReAct agent that recovers
from tool failures, a chunker, a vector search, a retrieval pipeline, a router across
specialists, and an eval harness that grades a whole trace rather than one reply. Then the
machinery a framework would otherwise hide: channels with reducers, a super-step scheduler, a
checkpointer with resume and time travel, handoffs, guardrails, and a validator wired back
into the prompt. The two project modules put all of it to work end to end.

The `frameworks` track rebuilds two runtimes in miniature, because that is what makes their
documentation readable. Module 7 is LangGraph's graph runtime, down to the versions that
decide which node runs next. Module 8 is the loop the OpenAI Agents SDK and Pydantic AI wrap,
where a handoff turns out to be a tool call and typed output turns out to be a schema plus a
retry. Module 4, on the `agent` track, is the survey that introduces all three first. Nothing
is installed: like every other exercise, both run against `mockllm` with the standard library
alone.

### Data engineering

5 modules, 17 lessons and 13 graded exercises, in pure standard library Python.

One idea in five steps: a pipeline is a promise about data that has to keep being true
tomorrow, so every stage has to be re-runnable and every promise has to be checkable. Students
parse a delimited file by hand once, write coercions that can admit they failed, validate a
whole extract instead of one row, quarantine the failures instead of dropping them, load into
a table with constraints that refuse, read a query plan, count what a join threw away, make a
load idempotent behind a watermark, backfill with the same code as the daily run, resume a job
that died halfway, and then check row counts and freshness and write the promise down.

`docs/CURRICULUM.md` has the lesson-by-lesson map, which idea is introduced where and paid off
where, and the rules for changing any of it. Read it before adding or moving a lesson.

## Writing content

Content lives under `packages/learning/courses/`. A course is a directory with a
`course.yaml`, a `lib/`, and its modules:

```
courses/ai-agents/
├─ course.yaml                 id, version, order, tracks
├─ lib/
│  └─ mockllm.py               copied into every exercise workspace in this course
└─ modules/
   └─ 03-tool-use/
      ├─ module.yaml           id, version, track, difficulty, prerequisites
      ├─ 01-what-makes-an-agent.mdx
      ├─ 02-tool-schemas.mdx
      ├─ 03-the-react-loop.mdx
      ├─ 04-parallel-tool-calls.mdx
      ├─ 05-when-tools-fail.mdx
      └─ exercises/
         ├─ tool-schemas/
         ├─ react-loop/
         │  ├─ scaffold.py     the student's starting buffer, signatures only
         │  ├─ reference.py    a complete worked solution
         │  └─ test.py         the grader
         ├─ parallel-dispatch/
         └─ resilient-agent/
```

A course declares its own tracks, and a module's `track` has to name one of them. There is no
global list of tracks to widen, which is what lets an unrelated course use whatever words
actually describe it.

`lib/` is the course's support library. Its files are copied into every exercise workspace in
that course rather than installed, so a student needs nothing but an interpreter to run their
first test, and a course can ship whatever its exercises import without any other course
knowing about it.

The `NN-` prefix on a lesson file has to match its `order`, and the slug after it has to match
the slug in its `id`. Module ids carry their course (`ai-tool-use`), and lesson ids are
`<module-id>.<lesson-slug>`. A lesson claims an exercise in its frontmatter:

```yaml
exercise:
  id: react-loop
  timeboxMinutes: 30
```

Then:

```bash
pnpm content          # build and validate
pnpm content:watch    # revalidate on save
```

### The build is a gate

`pnpm content` exits non-zero on a schema violation, a duplicate id or order, a module naming
a track its course did not declare, a module id or exercise id that collides with one in
another course, a prerequisite naming a module that does not exist or that lives in another
course, a prerequisite cycle, a lesson claiming an exercise whose files are missing, or a
cross-lesson link pointing nowhere.

It also runs each exercise against the checks that only apply to code. An exercise fails if its
reference solution does not pass its own test, if the scaffold does pass it, if a signature has
drifted between the scaffold and the reference, or if anything imports a package that would
need installing.

Those run the real test against the real files in a throwaway directory. A broken exercise
cannot ship, which is the point of the whole pipeline.

### How exercises work

The student's working file is always `solution.py`. `scaffold.py` is copied to that name when
the exercise first opens, and `test.py` imports from it. Because the name is fixed, one test
file grades both the student's attempt and the reference solution, which is what makes the
build gate possible.

The AI course's `mockllm.py` is copied into every one of its exercise workspaces by the build
rather than installed, so a student needs nothing but a Python interpreter to run their first
test. Any course can do the same with its own `lib/`.

Exercises open on the scaffold, never on the answer. The reference exists and takes a
deliberate, confirmed click to reveal. Reading a working solution after a real attempt teaches
something; reading one instead of attempting does not. That policy has one accepted exception,
written down in `docs/CURRICULUM.md`.

## Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Build content, then run the site on :5173 |
| `pnpm dev:desktop` | Build content, then run the Tauri app |
| `pnpm dev:desktop:web` | The desktop UI in a browser, without Tauri |
| `pnpm build` | Production build of the site |
| `pnpm build:desktop` | Package the desktop app |
| `pnpm content` | Build and validate the course |
| `pnpm typecheck` | TypeScript across every package |
| `pnpm test:core` | The game engine: level curve, award keys, quests, seals, streaks |
| `pnpm test:rust` | The Rust test suite |
| `pnpm lint:rust` | Clippy, warnings as errors |

## Going to production

The site runs on local file storage out of the box. To move to Postgres, set both variables
and apply the schema:

```bash
cp apps/web/.env.example apps/web/.env.local
# fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, then:
psql "$DATABASE_URL" -f supabase/schema.sql
```

Also set `SESSION_SECRET`. Without it the server generates a key and writes it to
`.data/session-secret`, which is per machine and will not work across multiple instances.

The service role key is read only by `apps/web/lib/server/` and never reaches a browser or
the desktop bundle. Clients never talk to the database, so the API is the security boundary:
every route handler derives `user_id` from the session and none of them trust a user id
arriving in a request body. Row level security is enabled as a second layer, but nothing
depends on it.

## Requirements

Node 22.12+, pnpm 11. Python 3.10 or newer to run exercises. Rust only if you are building
the desktop app.
