-- ══════════════════════════════════════════════════════════════════
-- AURIX — Supabase Schema
-- Run this entire file in the Supabase SQL editor once.
-- All tables mirror the JSON structure exactly so the Python
-- compatibility layer can reconstruct the same nested dicts.
-- ══════════════════════════════════════════════════════════════════

-- ── Settings (singleton row, id always = 1) ──────────────────────
create table if not exists settings (
  id                    integer primary key default 1,
  name                  text    default 'Ayush',
  daily_sleep_goal      integer default 8,
  daily_water_goal      integer default 8,
  currency              text    default '₹',
  monthly_budget        numeric default 0,
  productivity_weights  jsonb   default '{"habits":40,"tasks":30,"study":30}',
  constraint settings_singleton check (id = 1)
);
insert into settings (id) values (1) on conflict do nothing;

-- ── Habits ───────────────────────────────────────────────────────
create table if not exists habits (
  id          integer primary key,
  name        text    not null,
  icon        text    default '',
  color       text    default '',
  category    text    default '',
  frequency   text    default 'daily',
  target      integer default 1,
  unit        text    default '',
  streak      integer default 0,
  created     text    default '',
  notes       text    default '',
  order_idx   integer default 0,
  subtasks    jsonb   default '[]',
  time_slots  jsonb   default '[]'
);

-- ── Habit logs: {date: [habit_id, ...]} → flat rows ─────────────
create table if not exists habit_logs (
  id        bigserial primary key,
  log_date  text    not null,
  habit_id  integer not null references habits(id) on delete cascade,
  unique(log_date, habit_id)
);

-- ── Expenses ─────────────────────────────────────────────────────
create table if not exists expenses (
  id              integer primary key,
  amount          numeric not null,
  category        text    default '',
  description     text    default '',
  date            text    not null,
  payment_method  text    default '',
  tag             text    default '',
  notes           text    default ''
);

-- ── Exams (top-level, contains nested subjects/chapters) ─────────
-- We store the ENTIRE exam tree as JSONB per exam for simplicity.
-- This perfectly preserves all nested fields without joins.
create table if not exists exams (
  id        integer primary key,
  name      text    not null,
  date      text    default '',
  type      text    default '',
  priority  text    default 'Medium',
  status    text    default 'Upcoming',
  notes     text    default '',
  subjects  jsonb   default '[]'   -- full nested subjects/chapters/sessions/revisions
);

-- ── Independent Subjects (not tied to an exam) ───────────────────
create table if not exists subjects (
  id          integer primary key,
  name        text    not null,
  priority    text    default 'Medium',
  status      text    default 'Not Started',
  weak_subject boolean default false,
  start_date  text    default '',
  notes       text    default '',
  reference_books  text default '',
  resource_links   text default '',
  revisions   jsonb   default '[]',
  chapters    jsonb   default '[]'  -- full nested chapters/sessions/revisions
);

-- ── Goals ────────────────────────────────────────────────────────
create table if not exists goals (
  id           integer primary key,
  title        text    not null,
  description  text    default '',
  category     text    default '',
  status       text    default 'Pending',
  target_year  text    default '',
  target_date  text    default '',
  motivation   text    default '',
  progress     integer default 0,
  linked_exams jsonb   default '[]',   -- list of exam ids
  milestones   jsonb   default '[]',
  created      text    default ''
);

-- ── Thoughts ─────────────────────────────────────────────────────
create table if not exists thoughts (
  id          integer primary key,
  title       text    default '',
  content     text    default '',
  type        text    default 'Thought',
  mood        text    default '',
  tags        jsonb   default '[]',
  date        text    default '',
  created_at  text    default '',
  pinned      boolean default false,
  favorite    boolean default false
);

-- ── Sleep Logs ───────────────────────────────────────────────────
create table if not exists sleep_logs (
  id          integer primary key,
  date        text    not null,
  hours       numeric default 0,
  bedtime     text    default '',
  wake_time   text    default '',
  quality     text    default '',
  notes       text    default ''
);

-- ── Workouts ─────────────────────────────────────────────────────
create table if not exists workouts (
  id          integer primary key,
  name        text    not null,
  category    text    default '',
  unit        text    default 'reps',
  target      numeric default 0,
  notes       text    default ''
);

-- ── Workout Logs: {date: [{workout_id, ...}]} → flat rows ────────
create table if not exists workout_logs (
  id              bigserial primary key,
  log_date        text    not null,
  workout_id      integer not null references workouts(id) on delete cascade,
  reps            numeric default 0,
  sets            numeric default 0,
  weight          numeric default 0,
  duration_minutes numeric default 0,
  notes           text    default '',
  logged_at       text    default ''
);

-- ── Tasks (kept for legacy/AI) ────────────────────────────────────
create table if not exists tasks (
  id          integer primary key,
  title       text    not null,
  date        text    default '',
  priority    text    default 'Medium',
  category    text    default '',
  completed   boolean default false,
  important   boolean default false,
  notes       text    default '',
  created     text    default ''
);

-- ── Mood Logs: {date: mood_str} → flat rows ──────────────────────
create table if not exists mood_logs (
  log_date  text    primary key,
  mood      text    not null
);

-- ── Notes: {date: [{id, text, ...}]} → flat rows ─────────────────
create table if not exists notes (
  id        bigserial primary key,
  note_date text    not null,
  note_id   integer not null,
  text      text    default '',
  created   text    default '',
  unique(note_date, note_id)
);

-- ── Remember ─────────────────────────────────────────────────────
create table if not exists remember (
  id          integer primary key,
  title       text    default '',
  content     text    default '',
  category    text    default '',
  tags        jsonb   default '[]',
  date        text    default '',
  created_at  text    default '',
  archived    boolean default false,
  important   boolean default false
);

-- ── AI Sessions ──────────────────────────────────────────────────
create table if not exists ai_sessions (
  id      bigserial primary key,
  user_msg text   default '',
  bot_msg  text   default '',
  ts       text   default '',
  action   jsonb  default 'null'
);

-- ── Active Sessions (singleton) ───────────────────────────────────
create table if not exists active_sessions (
  id      integer primary key default 1,
  study   jsonb   default 'null',
  sleep   jsonb   default 'null',
  constraint active_sessions_singleton check (id = 1)
);
insert into active_sessions (id) values (1) on conflict do nothing;

-- ── Journal Entries: {date: text} → flat rows ─────────────────────
create table if not exists journal_entries (
  entry_date  text    primary key,
  content     text    default ''
);

-- ── Water Logs: {date: count} → flat rows ─────────────────────────
create table if not exists water_logs (
  log_date  text    primary key,
  count     integer default 0
);

-- Enable Row Level Security (optional but recommended)
-- alter table habits enable row level security;
-- (configure policies based on your auth setup)
