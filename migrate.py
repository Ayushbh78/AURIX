#!/usr/bin/env python3
"""
migrate.py — One-time migration from data.json → Supabase  (v4)
================================================================
Run once after setting up your Supabase project and schema:

    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_KEY="your-service-role-key"
    python migrate.py [--file path/to/data.json] [--dry-run]

Safe to re-run: all inserts use upsert so no duplicates are created.
Covers ALL tables including the new habit_entries and focus_timer_sessions.
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Migrate AURIX data.json → Supabase")
parser.add_argument("--file",    default="data.json", help="Path to data.json")
parser.add_argument("--dry-run", action="store_true",  help="Print what would be migrated")
args = parser.parse_args()

DATA_FILE = args.file
DRY_RUN   = args.dry_run

if not os.path.exists(DATA_FILE):
    print(f"❌  File not found: {DATA_FILE}")
    sys.exit(1)

with open(DATA_FILE, "r") as f:
    data = json.load(f)

if DRY_RUN:
    print("🔍  DRY RUN — no data will be written\n")
    for key, val in data.items():
        if isinstance(val, list):
            print(f"  {key}: {len(val)} items")
        elif isinstance(val, dict):
            print(f"  {key}: {len(val)} keys")
        else:
            print(f"  {key}: {val!r}")
    sys.exit(0)

# ── Connect to Supabase ───────────────────────────────────────────────────────
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌  Set SUPABASE_URL and SUPABASE_KEY environment variables first.")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
print(f"✅  Connected to Supabase: {SUPABASE_URL}\n")

errors = []


def report(label, count):
    print(f"  ✔  {label}: {count} record(s)")


def err(label, e):
    msg = f"  ✘  {label}: {e}"
    print(msg)
    errors.append(msg)


def _d(v):
    """Normalise date → YYYY-MM-DD or ''."""
    if not v:
        return ""
    s = str(v).strip()
    for sep in ("T", " "):
        if sep in s:
            s = s.split(sep)[0]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return ""


def _f(v, default=0.0):
    if v is None or v == "":
        return float(default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _i(v, default=0):
    if v is None or v == "":
        return int(default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)


# ── 1. Settings + Budget ──────────────────────────────────────────────────────
print("── Settings & Budget")
try:
    s = data.get("settings", {})
    b = data.get("budget", {})
    sb.table("settings").upsert({
        "id":                   1,
        "name":                 s.get("name", "Ayush"),
        "daily_sleep_goal":     _i(s.get("daily_sleep_goal", 8)),
        "daily_water_goal":     _i(s.get("daily_water_goal", 8)),
        "currency":             b.get("currency", "₹"),
        "monthly_budget":       _f(b.get("monthly", 0)),
        "productivity_weights": s.get("productivity_weights", {"habits":40,"tasks":30,"study":30}),
        "tags":                 data.get("tags") or [],
        "milestones":           data.get("milestones") or [],
    }).execute()
    report("settings", 1)
except Exception as e:
    err("settings", e)

# ── 2. Habits ─────────────────────────────────────────────────────────────────
print("\n── Habits")
habits = data.get("habits", [])
for h in habits:
    try:
        sb.table("habits").upsert({
            "id":         _i(h["id"]),
            "name":       h.get("name", ""),
            "icon":       h.get("icon", ""),
            "color":      h.get("color", ""),
            "category":   h.get("category", ""),
            "frequency":  h.get("frequency", "daily"),
            "target":     h.get("target", 1),
            "unit":       h.get("unit", ""),
            "streak":     h.get("streak", 0),
            "created":    _d(h.get("created", "")),
            "notes":      h.get("notes", ""),
            "order_idx":  h.get("order_idx", 0),
            "subtasks":   h.get("subtasks") or [],
            "time_slots": h.get("time_slots") or [],
            "priority":   h.get("priority", "Medium"),
            "reminders":  h.get("reminders") or [],
        }).execute()
    except Exception as e:
        err(f"habit id={h.get('id')}", e)
report("habits", len(habits))

# ── 3. Habit logs ─────────────────────────────────────────────────────────────
print("\n── Habit Logs")
habit_logs = data.get("habit_logs", {})
count = 0
for log_date, habit_ids in habit_logs.items():
    for hid in habit_ids:
        try:
            sb.table("habit_logs").upsert({
                "log_date": log_date,
                "habit_id": _i(hid),
            }).execute()
            count += 1
        except Exception as e:
            err(f"habit_log {log_date}/{hid}", e)
report("habit_log rows", count)

# ── 4. Habit entries ──────────────────────────────────────────────────────────
print("\n── Habit Entries")
habit_entries = data.get("habit_entries", {})
count = 0
for hid_str, entries in habit_entries.items():
    hid = _i(hid_str)
    for entry in entries:
        edate = _d(entry.get("date", ""))
        if not edate:
            continue
        try:
            sb.table("habit_entries").upsert({
                "habit_id":   hid,
                "entry_date": edate,
                "sub_tasks":  entry.get("sub_tasks") or [],
                "time_slots": entry.get("time_slots") or [],
                "notes":      entry.get("notes", ""),
            }).execute()
            count += 1
        except Exception as e:
            err(f"habit_entry hid={hid} date={edate}", e)
report("habit_entry rows", count)

# ── 5. Expenses ───────────────────────────────────────────────────────────────
print("\n── Expenses")
expenses = data.get("expenses", [])
for e in expenses:
    try:
        sb.table("expenses").upsert({
            "id":             _i(e["id"]),
            "amount":         _f(e.get("amount", 0)),
            "category":       e.get("category", ""),
            "description":    e.get("description", ""),
            "date":           _d(e.get("date", "")),
            "payment_method": e.get("payment_method", ""),
            "tag":            e.get("tag", ""),
            "notes":          e.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"expense id={e.get('id')}", ex)
report("expenses", len(expenses))

# ── 6. Exams ──────────────────────────────────────────────────────────────────
print("\n── Exams")
exams = data.get("exams", [])
for e in exams:
    try:
        sb.table("exams").upsert({
            "id":       _i(e["id"]),
            "name":     e.get("name", ""),
            "date":     _d(e.get("date", "")),
            "type":     e.get("type", ""),
            "priority": e.get("priority", "Medium"),
            "status":   e.get("status", "Upcoming"),
            "notes":    e.get("notes", ""),
            "subjects": e.get("subjects") or [],
        }).execute()
    except Exception as ex:
        err(f"exam id={e.get('id')}", ex)
report("exams", len(exams))

# ── 7. Independent Subjects ───────────────────────────────────────────────────
print("\n── Independent Subjects")
subjects = data.get("subjects", [])
for s in subjects:
    try:
        sb.table("subjects").upsert({
            "id":              _i(s["id"]),
            "name":            s.get("name", ""),
            "priority":        s.get("priority", "Medium"),
            "status":          s.get("status", "Not Started"),
            "weak_subject":    bool(s.get("weak_subject", False)),
            "start_date":      _d(s.get("start_date", "")),
            "notes":           s.get("notes", ""),
            "reference_books": s.get("reference_books", ""),
            "resource_links":  s.get("resource_links", ""),
            "revisions":       s.get("revisions") or [],
            "chapters":        s.get("chapters") or [],
        }).execute()
    except Exception as ex:
        err(f"subject id={s.get('id')}", ex)
report("subjects", len(subjects))

# ── 8. Goals ──────────────────────────────────────────────────────────────────
print("\n── Goals")
goals = data.get("goals", [])
for g in goals:
    try:
        sb.table("goals").upsert({
            "id":           _i(g["id"]),
            "title":        g.get("title", ""),
            "description":  g.get("description", ""),
            "category":     g.get("category", ""),
            "status":       g.get("status", "Pending"),
            "target_year":  g.get("target_year", ""),
            "target_date":  _d(g.get("target_date", "")),
            "motivation":   g.get("motivation", ""),
            "progress":     _i(g.get("progress", 0)),
            "linked_exams": g.get("linked_exams") or [],
            "milestones":   g.get("milestones") or [],
            "created":      _d(g.get("created", "")),
        }).execute()
    except Exception as ex:
        err(f"goal id={g.get('id')}", ex)
report("goals", len(goals))

# ── 9. Thoughts ───────────────────────────────────────────────────────────────
print("\n── Thoughts")
thoughts = data.get("thoughts", [])
for t in thoughts:
    try:
        sb.table("thoughts").upsert({
            "id":         _i(t["id"]),
            "title":      t.get("title", ""),
            "content":    t.get("content", ""),
            "type":       t.get("type", "Thought"),
            "mood":       t.get("mood", ""),
            "tags":       t.get("tags") or [],
            "date":       _d(t.get("date", "")),
            "created_at": t.get("created_at", ""),
            "pinned":     bool(t.get("pinned", False)),
            "favorite":   bool(t.get("favorite", False)),
        }).execute()
    except Exception as ex:
        err(f"thought id={t.get('id')}", ex)
report("thoughts", len(thoughts))

# ── 10. Sleep logs ────────────────────────────────────────────────────────────
print("\n── Sleep Logs")
sleep_logs = data.get("sleep_logs", [])
for sl in sleep_logs:
    try:
        sb.table("sleep_logs").upsert({
            "id":        _i(sl["id"]),
            "date":      _d(sl.get("date", "")),
            "hours":     _f(sl.get("hours", 0)),
            "bedtime":   sl.get("bedtime", ""),
            "wake_time": sl.get("wake_time", ""),
            "quality":   sl.get("quality", ""),
            "notes":     sl.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"sleep_log id={sl.get('id')}", ex)
report("sleep_logs", len(sleep_logs))

# ── 11. Workouts ──────────────────────────────────────────────────────────────
print("\n── Workouts")
workouts = data.get("workouts", [])
for w in workouts:
    try:
        sb.table("workouts").upsert({
            "id":       _i(w["id"]),
            "name":     w.get("name", ""),
            "category": w.get("category", ""),
            "unit":     w.get("unit", "reps"),
            "target":   _f(w.get("target", 0)),
            "notes":    w.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"workout id={w.get('id')}", ex)
report("workouts", len(workouts))

# ── 12. Workout logs ──────────────────────────────────────────────────────────
print("\n── Workout Logs")
workout_logs = data.get("workout_logs", {})
count = 0
for log_date, entries in workout_logs.items():
    for entry in entries:
        try:
            sb.table("workout_logs").insert({
                "log_date":         _d(log_date),
                "workout_id":       _i(entry["workout_id"]),
                "reps":             _f(entry.get("reps", 0)),
                "sets":             _f(entry.get("sets", 0)),
                "weight":           _f(entry.get("weight", 0)),
                "duration_minutes": _f(entry.get("duration_minutes", 0)),
                "notes":            entry.get("notes", ""),
                "logged_at":        entry.get("logged_at", ""),
            }).execute()
            count += 1
        except Exception as ex:
            err(f"workout_log {log_date}", ex)
report("workout_log rows", count)

# ── 13. Tasks ─────────────────────────────────────────────────────────────────
print("\n── Tasks")
tasks = data.get("tasks", [])
for t in tasks:
    try:
        sb.table("tasks").upsert({
            "id":        _i(t["id"]),
            "title":     t.get("title", ""),
            "date":      _d(t.get("date", "")),
            "priority":  t.get("priority", "Medium"),
            "category":  t.get("category", ""),
            "completed": bool(t.get("completed", False)),
            "important": bool(t.get("important", False)),
            "notes":     t.get("notes", ""),
            "created":   _d(t.get("created", "")),
        }).execute()
    except Exception as ex:
        err(f"task id={t.get('id')}", ex)
report("tasks", len(tasks))

# ── 14. Mood logs ─────────────────────────────────────────────────────────────
print("\n── Mood Logs")
mood_logs = data.get("mood_logs", {})
for log_date, mood in mood_logs.items():
    try:
        sb.table("mood_logs").upsert({"log_date": _d(log_date), "mood": mood}).execute()
    except Exception as ex:
        err(f"mood_log {log_date}", ex)
report("mood_logs", len(mood_logs))

# ── 15. Notes ─────────────────────────────────────────────────────────────────
print("\n── Notes")
notes = data.get("notes", {})
count = 0
for note_date, note_list in notes.items():
    for note in note_list:
        try:
            sb.table("notes").upsert({
                "note_date": _d(note_date),
                "note_id":   _i(note.get("id", 0)),
                "text":      note.get("text", ""),
                "created":   note.get("created", ""),
            }).execute()
            count += 1
        except Exception as ex:
            err(f"note {note_date}/{note.get('id')}", ex)
report("notes", count)

# ── 16. Journal entries ───────────────────────────────────────────────────────
print("\n── Journal Entries")
journal = data.get("journal_entries", {})
for entry_date, content in journal.items():
    try:
        sb.table("journal_entries").upsert({
            "entry_date": _d(entry_date),
            "content":    content,
        }).execute()
    except Exception as ex:
        err(f"journal {entry_date}", ex)
report("journal_entries", len(journal))

# ── 17. Water logs ────────────────────────────────────────────────────────────
print("\n── Water Logs")
water_logs = data.get("water_logs", {})
for log_date, count_val in water_logs.items():
    try:
        sb.table("water_logs").upsert({
            "log_date": _d(log_date),
            "count":    _i(count_val),
        }).execute()
    except Exception as ex:
        err(f"water_log {log_date}", ex)
report("water_logs", len(water_logs))

# ── 18. Remember ──────────────────────────────────────────────────────────────
# IMPORTANT: app uses "description"/"type"/"status" but DB uses "content"/"category"/"archived"
print("\n── Remember")
remember = data.get("remember", [])
for r in remember:
    try:
        sb.table("remember").upsert({
            "id":         _i(r["id"]),
            "title":      r.get("title", ""),
            # Map app field names → DB column names:
            "content":    r.get("description", r.get("content", "")),
            "category":   r.get("type", r.get("category", "Other")) or "Other",
            "tags":       r.get("tags") or [],
            "created_at": r.get("created_at", ""),
            "archived":   r.get("status", "Active") == "Archived" if "status" in r else bool(r.get("archived", False)),
            "important":  bool(r.get("important", False)),
        }).execute()
    except Exception as ex:
        err(f"remember id={r.get('id')}", ex)
report("remember", len(remember))

# ── 19. Focus timer sessions ──────────────────────────────────────────────────
print("\n── Focus Timer Sessions")
focus_sessions = data.get("focus_timer_sessions", [])
count = 0
for s in focus_sessions:
    try:
        sb.table("focus_timer_sessions").upsert({
            "id":           _i(s.get("id", 0)),
            "session_date": _d(s.get("date", "")),
            "subject_name": s.get("subject_name", ""),
            "chapter_name": s.get("chapter_name", ""),
            "duration_mins": _f(s.get("duration_mins", 0)),
            "start_time":   s.get("start_time", ""),
            "end_time":     s.get("end_time", ""),
            "notes":        s.get("notes", ""),
            "session_type": s.get("type", "focus"),
        }).execute()
        count += 1
    except Exception as ex:
        err(f"focus_timer_session id={s.get('id')}", ex)
report("focus_timer_sessions", count)

# ── 20. Active sessions ───────────────────────────────────────────────────────
print("\n── Active Sessions")
try:
    act       = data.get("active_sessions", {})
    study_val = act.get("study")
    if isinstance(study_val, dict):
        study_val = [study_val] if study_val else []
    elif not isinstance(study_val, list):
        study_val = []
    sb.table("active_sessions").upsert({
        "id":    1,
        "study": study_val,
        "sleep": act.get("sleep"),
    }).execute()
    report("active_sessions", 1)
except Exception as ex:
    err("active_sessions", ex)

# ── 21. Notification history ──────────────────────────────────────────────────
print("\n── Notification History")
notifs = data.get("notification_history", [])
count = 0
for n in notifs:
    try:
        sb.table("notification_history").insert({
            "title": n.get("title", ""),
            "body":  n.get("body", ""),
            "type":  n.get("type", "info"),
            "url":   n.get("url", "/"),
            "ts":    n.get("ts", ""),
            "read":  bool(n.get("read", False)),
        }).execute()
        count += 1
    except Exception as ex:
        err(f"notification id={n.get('id')}", ex)
report("notification_history", count)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "═" * 50)
if errors:
    print(f"⚠️  Migration completed with {len(errors)} error(s):")
    for e in errors:
        print(f"   {e}")
else:
    print("🎉  Migration completed successfully — zero errors!")
print("═" * 50)
print("\nNext steps:")
print("  1. Verify data in Supabase dashboard")
print("  2. Set SUPABASE_URL and SUPABASE_KEY in your production environment")
print("  3. Run your Flask app (no AURIX_USE_JSON=1 in production)")
print("  4. Verify all features work in the browser")
