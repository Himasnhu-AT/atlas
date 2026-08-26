# Learn Platform Handoff — Updated 2026-08-26

## Completed

### Content and exercise quality

- Audited all four courses: AI agents, data engineering, intro programming, and quantitative trading.
- Fixed contradictory course guidance, stale placeholder markers, unclear checkpointing and telemetry wording, and incomplete risk-performance explanations.
- Corrected scaffold/reference/test mismatches across data-engineering and quant-trading exercises.
- Added missing edge cases and clearer failure diagnostics for CSV handling, field coercion, incremental watermarks, freshness checks, row contracts, order books, drawdowns, performance metrics, VaR/CVaR, deflated Sharpe, dollar bars, and fractional differentiation.
- Fixed quant-trading reference implementations for timestamp normalization, tail-risk calculations, floating-point-sensitive trial counts, and boundary conditions.
- Resolved the order-book lifecycle contract: submitted IDs cannot be reused, while a partially filled taker remains resting and cancellable until its remainder is gone.
- Reconciled Sharpe/Sortino formulas, reference implementation, scaffold guidance, and tests around one excess-return convention: population dispersion, with MAR measured against the risk-free-adjusted return series.
- Removed an accidental generated `solution.py` from the momentum-signals exercise.
- Ensured AI-agent material remains offline/mock-only and preserves intended browser compatibility.

### Tauri desktop UI

- Aligned desktop typography, spacing, controls, banners, diagnostics, file tree, lesson pane, navigation, and status treatment with the redesigned website.
- Preserved the three-pane IDE model while improving focus/hover states, touch targets, responsive wrapping, accessible labels, and status semantics.

## Validation Status at Handoff

- `pnpm install --frozen-lockfile` — passed.
- `pnpm content:check` — passed: 4 courses, 31 modules, 122 lessons, 101 exercises.
- `pnpm content` / manifest rebuild — passed.
- `pnpm typecheck` — passed for all workspace packages/apps.
- `pnpm lint` — passed.
- `pnpm test:core` — passed: 103 tests.
- `pnpm test:content` — passed: 7 tests.
- `pnpm build` — passed; Next.js production site built successfully.
- `pnpm build:desktop` — passed; produced both macOS app and DMG bundles.

## Remaining Before Merge

All implementation and validation work is complete. The remaining work is review/staging only:

1. Review the broad uncommitted branch as one coherent change set. It now includes the website redesign/auth migration work in addition to content fixes, desktop UI parity, and the new intro-programming course.
2. Review all 124 files under the untracked `packages/learning/courses/intro-programming/`, excluding generated `__pycache__` directories before staging.
3. Confirm whether deleting `supabase/schema.sql`, replacing Supabase dependencies/configuration with Firebase artifacts, and adding admin routes are intentionally part of this branch.
4. Decide whether `HANDOFF.md` should be committed or removed after handoff.

## Notes for Tomorrow

- The working tree also contains pre-existing uncommitted website redesign changes under `apps/web`, plus README and curriculum documentation updates. Review them together rather than assuming every modified file belongs to this handoff session.
- `intro-programming` is entirely untracked because it is new course content; review its full file set before staging.
- A sandboxed `pnpm content` may fail with `EPERM` when `tsx` creates its temporary IPC pipe. Run it outside the sandbox or use the approved `pnpm content:check` path where possible.
