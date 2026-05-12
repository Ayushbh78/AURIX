#!/usr/bin/env python3
"""
migrate.py — One-time migration from data.json → Supabase
==========================================================
Run once after setting up your Supabase project and tables:

    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_KEY="your-service-role-key"
    python migrate.py [--file path/to/data.json]

The script reads data.json, inserts all records into Supabase, and
reports what was migrated. It is safe to run multiple times (upserts).
"""

import argparse
import json
import os
import sys
from datetime import datetime

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Migrate AURIX data.json → Supabase")
parser.add_argument("--file", default="data.json", help="Path to data.json")
parser.add_argument("--dry-run", action="store_true", help="Print what would be migrated")
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

# ── 1. Settings + Budget ──────────────────────────────────────────────────────
print("── Settings & Budget")
try:
    s = data.get("settings", {})
    b = data.get("budget", {})
    sb.table("settings").upsert({
        "id": 1,
        "name":                 s.get("name", "Ayush"),
        "daily_sleep_goal":     s.get("daily_sleep_goal", 8),
        "daily_water_goal":     s.get("daily_water_goal", 8),
        "currency":             b.get("currency", "₹"),
        "monthly_budget":       b.get("monthly", 0),
        "productivity_weights": s.get("productivity_weights", {"habits":40,"tasks":30,"study":30}),
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
            "id":         h["id"],
            "name":       h.get("name", ""),
            "icon":       h.get("icon", ""),
            "color":      h.get("color", ""),
            "category":   h.get("category", ""),
            "frequency":  h.get("frequency", "daily"),
            "target":     h.get("target", 1),
            "unit":       h.get("unit", ""),
            "created":    h.get("created", ""),
            "notes":      h.get("notes", ""),
            "order_idx":  h.get("order_idx", 0),
            "subtasks":   h.get("subtasks", []),
            "time_slots": h.get("time_slots", []),
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
                "habit_id": hid,
            }).execute()
            count += 1
        except Exception as e:
            err(f"habit_log {log_date}/{hid}", e)
report("habit_log rows", count)

# ── 4. Expenses ───────────────────────────────────────────────────────────────
print("\n── Expenses")
expenses = data.get("expenses", [])
for e in expenses:
    try:
        sb.table("expenses").upsert({
            "id":             e["id"],
            "amount":         e.get("amount", 0),
            "category":       e.get("category", ""),
            "description":    e.get("description", ""),
            "date":           e.get("date", ""),
            "payment_method": e.get("payment_method", ""),
            "tag":            e.get("tag", ""),
            "notes":          e.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"expense id={e.get('id')}", ex)
report("expenses", len(expenses))

# ── 5. Exams (full nested tree as JSONB) ──────────────────────────────────────
print("\n── Exams")
exams = data.get("exams", [])
for e in exams:
    try:
        sb.table("exams").upsert({
            "id":       e["id"],
            "name":     e.get("name", ""),
            "date":     e.get("date", ""),
            "type":     e.get("type", ""),
            "priority": e.get("priority", "Medium"),
            "status":   e.get("status", "Upcoming"),
            "notes":    e.get("notes", ""),
            "subjects": e.get("subjects", []),
        }).execute()
    except Exception as ex:
        err(f"exam id={e.get('id')}", ex)
report("exams", len(exams))

# ── 6. Independent Subjects ───────────────────────────────────────────────────
print("\n── Independent Subjects")
subjects = data.get("subjects", [])
for s in subjects:
    try:
        sb.table("subjects").upsert({
            "id":              s["id"],
            "name":            s.get("name", ""),
            "priority":        s.get("priority", "Medium"),
            "status":          s.get("status", "Not Started"),
            "weak_subject":    s.get("weak_subject", False),
            "start_date":      s.get("start_date", ""),
            "notes":           s.get("notes", ""),
            "reference_books": s.get("reference_books", ""),
            "resource_links":  s.get("resource_links", ""),
            "revisions":       s.get("revisions", []),
            "chapters":        s.get("chapters", []),
        }).execute()
    except Exception as ex:
        err(f"subject id={s.get('id')}", ex)
report("subjects", len(subjects))

# ── 7. Goals ──────────────────────────────────────────────────────────────────
print("\n── Goals")
goals = data.get("goals", [])
for g in goals:
    try:
        sb.table("goals").upsert({
            "id":           g["id"],
            "title":        g.get("title", ""),
            "description":  g.get("description", ""),
            "category":     g.get("category", ""),
            "status":       g.get("status", "Pending"),
            "target_year":  g.get("target_year", ""),
            "target_date":  g.get("target_date", ""),
            "motivation":   g.get("motivation", ""),
            "progress":     g.get("progress", 0),
            "linked_exams": g.get("linked_exams", []),
            "milestones":   g.get("milestones", []),
            "created":      g.get("created", ""),
        }).execute()
    except Exception as ex:
        err(f"goal id={g.get('id')}", ex)
report("goals", len(goals))

# ── 8. Thoughts ───────────────────────────────────────────────────────────────
print("\n── Thoughts")
thoughts = data.get("thoughts", [])
for t in thoughts:
    try:
        sb.table("thoughts").upsert({
            "id":         t["id"],
            "title":      t.get("title", ""),
            "content":    t.get("content", ""),
            "type":       t.get("type", "Thought"),
            "mood":       t.get("mood", ""),
            "tags":       t.get("tags", []),
            "date":       t.get("date", ""),
            "created_at": t.get("created_at", ""),
            "pinned":     t.get("pinned", False),
            "favorite":   t.get("favorite", False),
        }).execute()
    except Exception as ex:
        err(f"thought id={t.get('id')}", ex)
report("thoughts", len(thoughts))

# ── 9. Sleep logs ─────────────────────────────────────────────────────────────
print("\n── Sleep Logs")
sleep_logs = data.get("sleep_logs", [])
for sl in sleep_logs:
    try:
        sb.table("sleep_logs").upsert({
            "id":        sl["id"],
            "date":      sl.get("date", ""),
            "hours":     sl.get("hours", 0),
            "bedtime":   sl.get("bedtime", ""),
            "wake_time": sl.get("wake_time", ""),
            "quality":   sl.get("quality", ""),
            "notes":     sl.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"sleep_log id={sl.get('id')}", ex)
report("sleep_logs", len(sleep_logs))

# ── 10. Workouts ──────────────────────────────────────────────────────────────
print("\n── Workouts")
workouts = data.get("workouts", [])
for w in workouts:
    try:
        sb.table("workouts").upsert({
            "id":       w["id"],
            "name":     w.get("name", ""),
            "category": w.get("category", ""),
            "unit":     w.get("unit", "reps"),
            "target":   w.get("target", 0),
            "notes":    w.get("notes", ""),
        }).execute()
    except Exception as ex:
        err(f"workout id={w.get('id')}", ex)
report("workouts", len(workouts))

# ── 11. Workout logs ──────────────────────────────────────────────────────────
print("\n── Workout Logs")
workout_logs = data.get("workout_logs", {})
count = 0
for log_date, entries in workout_logs.items():
    for entry in entries:
        try:
            sb.table("workout_logs").insert({
                "log_date":         log_date,
                "workout_id":       entry["workout_id"],
                "reps":             entry.get("reps", 0),
                "sets":             entry.get("sets", 0),
                "weight":           entry.get("weight", 0),
                "duration_minutes": entry.get("duration_minutes", 0),
                "notes":            entry.get("notes", ""),
                "logged_at":        entry.get("logged_at", ""),
            }).execute()
            count += 1
        except Exception as ex:
            err(f"workout_log {log_date}", ex)
report("workout_log rows", count)

# ── 12. Tasks ─────────────────────────────────────────────────────────────────
print("\n── Tasks")
tasks = data.get("tasks", [])
for t in tasks:
    try:
        sb.table("tasks").upsert({
            "id":        t["id"],
            "title":     t.get("title", ""),
            "date":      t.get("date", ""),
            "priority":  t.get("priority", "Medium"),
            "category":  t.get("category", ""),
            "completed": t.get("completed", False),
            "important": t.get("important", False),
            "notes":     t.get("notes", ""),
            "created":   t.get("created", ""),
        }).execute()
    except Exception as ex:
        err(f"task id={t.get('id')}", ex)
report("tasks", len(tasks))

# ── 13. Mood logs ─────────────────────────────────────────────────────────────
print("\n── Mood Logs")
mood_logs = data.get("mood_logs", {})
for log_date, mood in mood_logs.items():
    try:
        sb.table("mood_logs").upsert({"log_date": log_date, "mood": mood}).execute()
    except Exception as ex:
        err(f"mood_log {log_date}", ex)
report("mood_logs", len(mood_logs))

# ── 14. Notes ─────────────────────────────────────────────────────────────────
print("\n── Notes")
notes = data.get("notes", {})
count = 0
for note_date, note_list in notes.items():
    for note in note_list:
        try:
            sb.table("notes").upsert({
                "note_date": note_date,
                "note_id":   note.get("id", 0),
                "text":      note.get("text", ""),
                "created":   note.get("created", ""),
            }).execute()
            count += 1
        except Exception as ex:
            err(f"note {note_date}/{note.get('id')}", ex)
report("notes", count)

# ── 15. Journal entries ───────────────────────────────────────────────────────
print("\n── Journal Entries")
journal = data.get("journal_entries", {})
for entry_date, content in journal.items():
    try:
        sb.table("journal_entries").upsert({
            "entry_date": entry_date,
            "content":    content,
        }).execute()
    except Exception as ex:
        err(f"journal {entry_date}", ex)
report("journal_entries", len(journal))

# ── 16. Water logs ────────────────────────────────────────────────────────────
print("\n── Water Logs")
water_logs = data.get("water_logs", {})
for log_date, count_val in water_logs.items():
    try:
        sb.table("water_logs").upsert({
            "log_date": log_date,
            "count":    count_val,
        }).execute()
    except Exception as ex:
        err(f"water_log {log_date}", ex)
report("water_logs", len(water_logs))

# ── 17. Remember ─────────────────────────────────────────────────────────────
print("\n── Remember")
remember = data.get("remember", [])
for r in remember:
    try:
        sb.table("remember").upsert({
            "id":         r["id"],
            "title":      r.get("title", ""),
            "content":    r.get("content", ""),
            "category":   r.get("category", ""),
            "tags":       r.get("tags", []),
            "date":       r.get("date", ""),
            "created_at": r.get("created_at", ""),
            "archived":   r.get("archived", False),
            "important":  r.get("important", False),
        }).execute()
    except Exception as ex:
        err(f"remember id={r.get('id')}", ex)
report("remember", len(remember))

# ── 19. Active sessions ───────────────────────────────────────────────────────
print("\n── Active Sessions")
try:
    act = data.get("active_sessions", {})
    sb.table("active_sessions").upsert({
        "id":    1,
        "study": act.get("study"),
        "sleep": act.get("sleep"),
    }).execute()
    report("active_sessions", 1)
except Exception as ex:
    err("active_sessions", ex)

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
print("  1. Set SUPABASE_URL and SUPABASE_KEY in your environment")
print("  2. Run your Flask app (remove AURIX_USE_JSON=1 if set)")
print("  3. Verify all features work in the browser")
