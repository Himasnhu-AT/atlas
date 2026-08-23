-- Atlas: schema.
--
-- Content bodies are never stored here. Lessons and exercises live in
-- packages/learning and ship inside both apps. `modules` is a registry, not
-- content: it tells the backend what is live, at what version, and what
-- unlocks what.
--
-- Clients never connect to this database. The Next.js API holds the service
-- role key and derives user_id from the session on every request, so the API
-- is the security boundary. RLS below is a second layer, not the primary one.

create extension if not exists "pgcrypto";

-- Users -----------------------------------------------------------------

create table if not exists users (
  id             text primary key,
  email          text not null unique,
  display_name   text not null,
  avatar_url     text,
  password_hash  text not null,
  password_salt  text not null,
  created_at     timestamptz not null default now(),
  last_seen_at   timestamptz
);

create index if not exists users_email_lower_idx on users (lower(email));

-- Course and module registry --------------------------------------------
-- Written only by a deploy-time sync from the content manifest.

create table if not exists courses (
  id         text primary key,
  slug       text not null unique,
  name       text not null,
  version    text not null,
  is_active  boolean not null default true,
  "order"    integer not null,
  updated_at timestamptz not null default now()
);

create table if not exists modules (
  id              text primary key,
  course_id       text not null references courses (id) on delete cascade,
  slug            text not null,
  name            text not null,
  version         text not null,
  is_active       boolean not null default true,
  prerequisites   text[] not null default '{}',
  -- `track` is a grouping inside one course and deliberately carries no CHECK.
  -- It used to be constrained to the AI course's five words, which every later
  -- course would have had to either misuse or widen. A course declares its own
  -- tracks in `course.yaml`, and the content build refuses a module naming one
  -- its own course did not declare, so the constraint lives where the
  -- vocabulary does.
  track           text not null,
  "order"         integer not null,
  difficulty      text not null check (difficulty in ('beginner', 'intermediate', 'advanced')),
  estimated_hours numeric not null,
  updated_at      timestamptz not null default now(),
  -- Slugs only have to be unique inside a course: two courses may each have a
  -- `foundations`. The URL always carries both, so this is the real key.
  unique (course_id, slug)
);

create index if not exists modules_course_idx on modules (course_id, "order");

-- Progress --------------------------------------------------------------

create table if not exists module_progress (
  user_id           text not null references users (id) on delete cascade,
  module_id         text not null references modules (id) on delete cascade,
  status            text not null default 'available'
                    check (status in ('locked', 'available', 'in_progress', 'completed')),
  lessons_completed integer not null default 0,
  lessons_total     integer not null default 0,
  started_at        timestamptz,
  completed_at      timestamptz,
  primary key (user_id, module_id)
);

-- lesson_id stays plain text: lessons live in the content bundle, not here.
-- The API validates it against the manifest before writing, so there are no
-- orphan rows even without a foreign key.
create table if not exists lesson_progress (
  user_id       text not null references users (id) on delete cascade,
  lesson_id     text not null,
  module_id     text not null references modules (id) on delete cascade,
  status        text not null default 'not_started'
                check (status in ('not_started', 'in_progress', 'completed')),
  seconds_spent integer not null default 0,
  started_at    timestamptz,
  completed_at  timestamptz,
  primary key (user_id, lesson_id)
);

create index if not exists lesson_progress_module_idx on lesson_progress (user_id, module_id);

-- The student's working buffer, so closing the app does not lose their work.
create table if not exists exercise_state (
  user_id             text not null references users (id) on delete cascade,
  exercise_id         text not null,
  current_code        text not null default '',
  peeked_reference_at timestamptz,
  updated_at          timestamptz not null default now(),
  primary key (user_id, exercise_id)
);

-- Append only. This history is what makes it possible to see where students
-- actually get stuck.
create table if not exists exercise_attempts (
  id           uuid primary key default gen_random_uuid(),
  user_id      text not null references users (id) on delete cascade,
  exercise_id  text not null,
  passed       boolean not null,
  tests_passed integer not null default 0,
  tests_total  integer not null default 0,
  duration_ms  integer not null default 0,
  stdout_tail  text,
  -- Client-generated id for one run, so replaying an offline outbox does not
  -- duplicate the log. Award keys dedupe the XP; they do not dedupe history, and
  -- "how many tries did this take" is the only reason this table exists.
  client_event_id text,
  created_at   timestamptz not null default now()
);

create unique index if not exists exercise_attempts_client_event_idx
  on exercise_attempts (user_id, client_event_id)
  where client_event_id is not null;

create index if not exists exercise_attempts_user_idx
  on exercise_attempts (user_id, exercise_id, created_at desc);

-- The game -------------------------------------------------------------
--
-- `xp_awards` is the ledger and the only authority on a total. Everything else
-- the game shows -- level, rank, streak, quest progress, seal eligibility -- is
-- derived from it and from the progress tables, so there is no second number to
-- reconcile and nothing to migrate when a weight changes.

create table if not exists xp_awards (
  user_id       text not null references users (id) on delete cascade,
  -- The idempotency key: a function of the user, the kind, and a natural key for
  -- the thing rewarded. Never a timestamp. `lesson:<id>:<completedAt>` looks
  -- right, passes every test where the learner completes once, and double-pays
  -- on the third toggle.
  award_key     text not null,
  kind          text not null check (kind in ('lesson','exercise','module','quest','streak','seal')),
  points        integer not null check (points > 0),
  -- Which version of the weights produced `points`, so a total can be explained
  -- later rather than only trusted.
  rules_version integer not null default 1,
  course_id     text,
  device_id     uuid,
  -- Client time, clamped server-side. Evidence, not authority.
  occurred_at   timestamptz not null default now(),
  -- Server receipt time. The leaderboard scores on this, so an offline backlog
  -- drained on Monday cannot retroactively win last week.
  awarded_at    timestamptz not null default now(),
  primary key (user_id, award_key)
);

create index if not exists xp_awards_user_awarded_idx on xp_awards (user_id, awarded_at desc);

create table if not exists user_game (
  user_id            text primary key references users (id) on delete cascade,
  -- A cache of sum(points). `xp_awards` is authoritative; this exists so a
  -- leaderboard does not aggregate the ledger per row.
  total_xp           integer not null default 0,
  -- Days a week the learner asked of themselves, and whether they actually
  -- picked it. There is deliberately no daily streak column: see
  -- packages/core/src/game/weekly.ts for why this product does not have one.
  weekly_target        integer not null default 3 check (weekly_target between 1 and 7),
  weekly_target_chosen boolean not null default false,
  best_weeks           integer not null default 0,
  leaderboard_opt_in boolean not null default false,
  -- IANA zone, captured at signup. The server assigns the day a piece of
  -- activity belongs to, so a client clock cannot decide what day it is.
  timezone           text not null default 'UTC',
  updated_at         timestamptz not null default now()
);

create table if not exists user_seals (
  user_id   text not null references users (id) on delete cascade,
  seal_id   text not null,
  course_id text,
  earned_at timestamptz not null default now(),
  primary key (user_id, seal_id)
);

-- Awards and the cached total move together or not at all.
--
-- The insert dedupes on the primary key; an unconditional `update ... set
-- total_xp = total_xp + n` beside it would not, so a double-click pays once into
-- the ledger and twice into the cache. Gating the update on the insert having
-- happened is the whole point of doing this in one statement.
create or replace function award_xp(
  p_user_id       text,
  p_award_key     text,
  p_kind          text,
  p_points        integer,
  p_course_id     text,
  p_rules_version integer,
  p_occurred_at   timestamptz
) returns integer
language plpgsql
as $$
declare
  v_inserted integer;
begin
  insert into xp_awards (user_id, award_key, kind, points, course_id, rules_version, occurred_at)
  values (p_user_id, p_award_key, p_kind, p_points, p_course_id, p_rules_version,
          coalesce(p_occurred_at, now()))
  on conflict (user_id, award_key) do nothing;

  get diagnostics v_inserted = row_count;
  if v_inserted = 0 then
    return 0;
  end if;

  insert into user_game (user_id, total_xp)
  values (p_user_id, p_points)
  on conflict (user_id) do update
    set total_xp = user_game.total_xp + excluded.total_xp,
        updated_at = now();

  return p_points;
end;
$$;

create table if not exists devices (
  id           uuid primary key default gen_random_uuid(),
  user_id      text not null references users (id) on delete cascade,
  name         text not null,
  platform     text not null,
  app_version  text not null,
  created_at   timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at   timestamptz
);

create table if not exists activity_days (
  user_id         text not null references users (id) on delete cascade,
  day             date not null,
  lessons_touched integer not null default 0,
  attempts        integer not null default 0,
  primary key (user_id, day)
);

-- Called by the API rather than doing a read-modify-write from the app, so two
-- concurrent requests on the same day cannot lose a count.
create or replace function bump_activity(
  p_user_id text,
  p_day     date,
  p_lessons integer,
  p_attempts integer
) returns void
language sql
as $$
  insert into activity_days (user_id, day, lessons_touched, attempts)
  values (p_user_id, p_day, p_lessons, p_attempts)
  on conflict (user_id, day) do update
    set lessons_touched = activity_days.lessons_touched + excluded.lessons_touched,
        attempts        = activity_days.attempts + excluded.attempts;
$$;

-- Row level security ----------------------------------------------------
--
-- Defence in depth. The service role bypasses these, and the API is what
-- actually enforces ownership. They matter if a key ever leaks or if a future
-- client connects directly.

alter table courses           enable row level security;
alter table xp_awards         enable row level security;
alter table user_game         enable row level security;
alter table user_seals        enable row level security;
alter table users             enable row level security;
alter table module_progress   enable row level security;
alter table lesson_progress   enable row level security;
alter table exercise_state    enable row level security;
alter table exercise_attempts enable row level security;
alter table devices           enable row level security;
alter table activity_days     enable row level security;
alter table modules           enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array[
    'module_progress', 'lesson_progress', 'exercise_state',
    'exercise_attempts', 'devices', 'activity_days',
    'xp_awards', 'user_game', 'user_seals'
  ] loop
    execute format(
      'create policy %I on %I for all using (user_id = auth.uid()::text) '
      'with check (user_id = auth.uid()::text)',
      t || '_own_rows', t
    );
  end loop;
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy users_own_row on users
    for select using (id = auth.uid()::text);
exception when duplicate_object then null;
end $$;

-- The registry is metadata about content that ships inside both apps anyway.
do $$
begin
  create policy modules_readable on modules for select using (true);
exception when duplicate_object then null;
end $$;

do $$
begin
  create policy courses_readable on courses for select using (true);
exception when duplicate_object then null;
end $$;
