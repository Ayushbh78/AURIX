-- ══════════════════════════════════════════════════════════════════════════════
-- AURIX — Supabase Schema  (v4 — production-ready)
-- Run this entire file in the Supabase SQL editor.
-- Safe to re-run: uses CREATE TABLE IF NOT EXISTS + ALTER TABLE IF NOT EXISTS.
-- All tables mirror the Python dict structure exactly.
-- ══════════════════════════════════════════════════════════════════════════════

-- ── Settings (singleton row, id always = 1) ───────────────────────────────────
create table if not exists settings (
  id                    integer primary key default 1,
  name                  text    default 'Ayush',
  daily_sleep_goal      integer default 8,
  daily_water_goal      integer default 8,
  currency              text    default '₹',
  monthly_budget        numeric default 0,
  productivity_weights  jsonb   default '{"habits":40,"tasks":30,"study":30}',
  -- top-level collections stored here to avoid extra tables
  tags                  jsonb   default '[]',
  milestones            jsonb   default '[]',
  constraint settings_singleton check (id = 1)
);
insert into settings (id) values (1) on conflict do nothing;

-- Safe migration: add missing columns if table already exists
alter table settings add column if not exists tags       jsonb default '[]';
alter table settings add column if not exists milestones jsonb default '[]';

-- ── Habits ────────────────────────────────────────────────────────────────────
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
  time_slots  jsonb   default '[]',
  priority    text    default 'Medium',
  reminders   jsonb   default '[]'
);
-- Safe migrations for existing installations
alter table habits add column if not exists priority   text  default 'Medium';
alter table habits add column if not exists reminders  jsonb default '[]';

-- ── Habit logs: {date: [habit_id, ...]} → flat rows ─────────────────────────
create table if not exists habit_logs (
  id        bigserial primary key,
  log_date  text    not null,
  habit_id  integer not null references habits(id) on delete cascade,
  unique(log_date, habit_id)
);

-- ── Habit entries: {str(habit_id): [{date, sub_tasks, time_slots, notes}]} ───
-- NEW TABLE — required for subtask/timeslot CRUD to persist
create table if not exists habit_entries (
  id          bigserial primary key,
  habit_id    integer not null references habits(id) on delete cascade,
  entry_date  text    not null,
  sub_tasks   jsonb   default '[]',
  time_slots  jsonb   default '[]',
  notes       text    default '',
  unique(habit_id, entry_date)
);

-- ── Expenses ──────────────────────────────────────────────────────────────────
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

-- ── Exams (full nested subjects/chapters as JSONB) ────────────────────────────
create table if not exists exams (
  id        integer primary key,
  name      text    not null,
  date      text    default '',
  type      text    default '',
  priority  text    default 'Medium',
  status    text    default 'Upcoming',
  notes     text    default '',
  subjects  jsonb   default '[]'
);

-- ── Independent Subjects ──────────────────────────────────────────────────────
create table if not exists subjects (
  id               integer primary key,
  name             text    not null,
  priority         text    default 'Medium',
  status           text    default 'Not Started',
  weak_subject     boolean default false,
  start_date       text    default '',
  notes            text    default '',
  reference_books  text    default '',
  resource_links   text    default '',
  revisions        jsonb   default '[]',
  chapters         jsonb   default '[]'
);

-- ── Goals ─────────────────────────────────────────────────────────────────────
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
  linked_exams jsonb   default '[]',
  milestones   jsonb   default '[]',
  created      text    default ''
);

-- ── Thoughts ──────────────────────────────────────────────────────────────────
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

-- ── Sleep Logs ────────────────────────────────────────────────────────────────
create table if not exists sleep_logs (
  id          integer primary key,
  date        text    not null,
  hours       numeric default 0,
  bedtime     text    default '',
  wake_time   text    default '',
  quality     text    default '',
  notes       text    default ''
);

-- ── Workouts ──────────────────────────────────────────────────────────────────
create table if not exists workouts (
  id          integer primary key,
  name        text    not null,
  category    text    default '',
  unit        text    default 'reps',
  target      numeric default 0,
  notes       text    default ''
);

-- ── Workout Logs: {date: [{workout_id, ...}]} → flat rows ────────────────────
create table if not exists workout_logs (
  id               bigserial primary key,
  log_date         text    not null,
  workout_id       integer not null references workouts(id) on delete cascade,
  reps             numeric default 0,
  sets             numeric default 0,
  weight           numeric default 0,
  duration_minutes numeric default 0,
  notes            text    default '',
  logged_at        text    default ''
);

-- ── Tasks ─────────────────────────────────────────────────────────────────────
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

-- ── Mood Logs: {date: mood_str} → flat rows ───────────────────────────────────
create table if not exists mood_logs (
  log_date  text    primary key,
  mood      text    not null
);

-- ── Notes: {date: [{id, text, ...}]} → flat rows ─────────────────────────────
create table if not exists notes (
  id        bigserial primary key,
  note_date text    not null,
  note_id   integer not null,
  text      text    default '',
  created   text    default '',
  unique(note_date, note_id)
);

-- ── Remember ──────────────────────────────────────────────────────────────────
-- DB columns: content, category, archived
-- App fields: description, type, status  (mapping handled in db.py)
create table if not exists remember (
  id          integer primary key,
  title       text    default '',
  content     text    default '',   -- app calls this "description"
  category    text    default '',   -- app calls this "type"
  tags        jsonb   default '[]',
  date        text    default '',
  created_at  text    default '',
  archived    boolean default false,
  important   boolean default false
);

-- ── Focus Timer Sessions ──────────────────────────────────────────────────────
-- NEW TABLE — required for focus_timer_sessions to persist
create table if not exists focus_timer_sessions (
  id            bigserial primary key,
  session_date  text    not null default '',
  subject_name  text    default '',
  chapter_name  text    default '',
  duration_mins numeric default 0,
  start_time    text    default '',
  end_time      text    default '',
  notes         text    default '',
  session_type  text    default 'focus'
);

-- ── Active Sessions (singleton) ───────────────────────────────────────────────
create table if not exists active_sessions (
  id    integer primary key default 1,
  study jsonb   default 'null',
  sleep jsonb   default 'null',
  constraint active_sessions_singleton check (id = 1)
);
insert into active_sessions (id) values (1) on conflict do nothing;

-- ── Journal Entries: {date: text} → flat rows ─────────────────────────────────
create table if not exists journal_entries (
  entry_date  text    primary key,
  content     text    default ''
);

-- ── Water Logs: {date: count} → flat rows ─────────────────────────────────────
create table if not exists water_logs (
  log_date  text    primary key,
  count     integer default 0
);

-- ── Notification History ──────────────────────────────────────────────────────
create table if not exists notification_history (
  id      bigserial primary key,
  title   text    default '',
  body    text    default '',
  type    text    default 'info',
  url     text    default '/',
  ts      text    default '',
  "read"  boolean default false
);

-- ── Indexes for performance ───────────────────────────────────────────────────
create index if not exists idx_habit_logs_date    on habit_logs    (log_date);
create index if not exists idx_habit_logs_habit   on habit_logs    (habit_id);
create index if not exists idx_habit_entries_hid  on habit_entries (habit_id);
create index if not exists idx_habit_entries_date on habit_entries (entry_date);
create index if not exists idx_workout_logs_date  on workout_logs  (log_date);
create index if not exists idx_tasks_date         on tasks         (date);
create index if not exists idx_expenses_date      on expenses      (date);
create index if not exists idx_thoughts_date      on thoughts      (date);
create index if not exists idx_sleep_logs_date    on sleep_logs    (date);
create index if not exists idx_focus_sessions_date on focus_timer_sessions (session_date);
create index if not exists idx_notif_ts           on notification_history (ts);

-- ── Row Level Security ────────────────────────────────────────────────────────
-- RLS is disabled by default so the service-role key works without policies.
-- Enable and configure policies if you add auth:
-- alter table habits enable row level security;
-- create policy "service role bypass" on habits using (true);
