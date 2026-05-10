from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime, date, timedelta

# Load .env file if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — use system environment variables

app = Flask(__name__)

# ─── Data Layer — Supabase ────────────────────────────────────────────────────
# load_data() and save_data() are now provided by db.py which connects to
# Supabase. The returned dict structure is identical to the old data.json so
# every route works unchanged.
#
# Set environment variables before running:
#   export SUPABASE_URL="https://xxxx.supabase.co"
#   export SUPABASE_KEY="your-service-role-or-anon-key"
#
# For local development without Supabase, set AURIX_USE_JSON=1 to fall back
# to the local data.json file.

_USE_JSON = os.environ.get("AURIX_USE_JSON", "").strip() == "1"

if _USE_JSON:
    # ── JSON fallback (local dev without Supabase) ─────────────────────────
    DATA_FILE = 'data.json'

    def default_data():
        return {
            "habits": [], "habit_logs": {}, "habit_entries": {},
            "expenses": [],
            "budget": {"monthly": 0, "currency": "₹"},
            "exams": [], "subjects": [], "notes": {}, "thoughts": [],
            "goals": [], "tasks": [], "sleep_logs": [], "focus_sessions": [],
            "mood_logs": {}, "water_logs": {}, "journal_entries": {},
            "workouts": [], "workout_logs": {}, "focus_timer_sessions": [],
            "ai_sessions": [], "remember": [],
            "active_sessions": {"study": None, "sleep": None},
            "settings": {
                "name": "Ayush", "daily_sleep_goal": 8, "daily_water_goal": 8,
                "productivity_weights": {"habits": 40, "tasks": 30, "study": 30}
            },
            "milestones": [], "tags": [],
        }

    def load_data():
        if not os.path.exists(DATA_FILE):
            save_data(default_data())
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        defaults = default_data()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        return data

    def save_data(data):
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)

else:
    # ── Supabase (production) ──────────────────────────────────────────────
    from db import load_data, save_data


from datetime import datetime, date, timedelta, timezone

# IST = UTC+5:30
_IST = timezone(timedelta(hours=5, minutes=30))

def today_str():
    """Return today's date in IST (India Standard Time), not UTC."""
    return datetime.now(_IST).strftime("%Y-%m-%d")

def get_id(collection):
    if not collection:
        return 1
    return max(item.get('id', 0) for item in collection) + 1

# ─── Productivity Score ───────────────────────────────────────────────────────

def calc_productivity_score(data, date_str=None):
    if not date_str:
        date_str = today_str()
    score = 0
    has_any_data = False

    # Habits (40%) — counted once only
    habits = data.get('habits', [])
    logs = data.get('habit_logs', {}).get(date_str, [])
    if habits and logs:
        has_any_data = True
        habit_score = (len(logs) / len(habits)) * 40
        score += habit_score

    # Tasks (30%)
    tasks = [t for t in data.get('tasks', []) if t.get('date') == date_str]
    if tasks:
        has_any_data = True
        done = [t for t in tasks if t.get('completed')]
        task_score = (len(done) / len(tasks)) * 30
        score += task_score

    # Study (30%) - chapters + study time
    all_chapters = []
    for exam in data.get('exams', []):
        for subj in exam.get('subjects', []):
            all_chapters.extend(subj.get('chapters', []))
    for subj in data.get('subjects', []):
        all_chapters.extend(subj.get('chapters', []))
    completed_today = [c for c in all_chapters if c.get('completion_date') == date_str]
    if completed_today:
        has_any_data = True
        study_score = min(len(completed_today) * 10, 30)
        score += study_score

    # Study sessions today
    for ch in all_chapters:
        for sess in ch.get('study_sessions', []):
            if sess.get('date') == date_str and sess.get('duration', 0) > 0:
                has_any_data = True
                score = min(score + sess['duration'] * 5, 100)

    # Exercise (bonus up to 15)
    workout_logs = data.get('workout_logs', {}).get(date_str, [])
    if workout_logs:
        has_any_data = True
        score = min(score + len(workout_logs) * 5, 100)

    if not has_any_data:
        return None  # No data - do not show score

    return round(min(score, 100))

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/dashboard')
def dashboard():
    data = load_data()
    today = today_str()
    
    # Habits
    habits = data['habits']
    logs_today = data['habit_logs'].get(today, [])
    habit_completion = round((len(logs_today) / len(habits) * 100) if habits else 0)
    
    # Streaks
    for h in habits:
        h['streak'] = calc_streak(data, h['id'])
    max_streak = max((h['streak'] for h in habits), default=0)

    # Spending
    expenses = data['expenses']
    today_spend = sum(e['amount'] for e in expenses if e['date'] == today)
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_spend = sum(e['amount'] for e in expenses if e['date'] >= week_start)
    month_start = date.today().replace(day=1).isoformat()
    month_spend = sum(e['amount'] for e in expenses if e['date'] >= month_start)
    budget = data['budget']['monthly']
    budget_remaining = budget - month_spend

    # Goals
    goals = data['goals']
    goals_completed = len([g for g in goals if g['status'] == 'Completed'])
    goals_pending = len([g for g in goals if g['status'] != 'Completed'])

    # Study
    all_exams = data['exams']
    all_subjects = data['subjects']
    for exam in all_exams:
        total = sum(len(s.get('chapters', [])) for s in exam.get('subjects', []))
        done = sum(1 for s in exam.get('subjects', []) for c in s.get('chapters', []) if c.get('status') == 'Completed')
        exam['progress'] = round(done / total * 100) if total else 0
        if exam.get('date'):
            try:
                delta = (datetime.strptime(exam['date'], '%Y-%m-%d').date() - date.today()).days
                exam['days_left'] = delta
            except:
                exam['days_left'] = None
        else:
            exam['days_left'] = None
    upcoming_exams = sorted(
        [e for e in all_exams if e.get('date', '')],
        key=lambda x: x['date']
    )[:5]

    total_chapters = 0
    completed_chapters = 0
    revision_pending = 0
    for exam in all_exams:
        for subj in exam.get('subjects', []):
            for ch in subj.get('chapters', []):
                total_chapters += 1
                if ch.get('status') == 'Completed':
                    completed_chapters += 1
                if ch.get('status') == 'Revision Pending':
                    revision_pending += 1
    for subj in all_subjects:
        for ch in subj.get('chapters', []):
            total_chapters += 1
            if ch.get('status') == 'Completed':
                completed_chapters += 1
            if ch.get('status') == 'Revision Pending':
                revision_pending += 1

    # Sleep
    sleep_logs = data['sleep_logs']
    last_sleep = sleep_logs[-1] if sleep_logs else None

    # Mood
    mood_today = data.get('mood_logs', {}).get(today)

    # Productivity
    prod_score = calc_productivity_score(data, today)
    weekly_scores = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        sc = calc_productivity_score(data, d)
        weekly_scores.append({'date': d, 'score': sc})

    # Thoughts
    all_thoughts = data.get('thoughts', [])
    thoughts_today = [t for t in all_thoughts if t.get('date') == today]
    thoughts_recent = sorted(all_thoughts, key=lambda x: x.get('created_at',''), reverse=True)[:3]

    # Exercise
    workout_logs_today = data.get('workout_logs', {}).get(today, [])
    exercise_done = len(workout_logs_today)
    total_workouts = len(data.get('workouts', []))
    exercise_mins_today = sum(l.get('duration_minutes', 0) for l in workout_logs_today)
    exercise_streak = 0
    _chk = date.today()
    while True:
        _d = _chk.isoformat()
        if data.get('workout_logs', {}).get(_d):
            exercise_streak += 1
            _chk -= timedelta(days=1)
        else:
            break

    # Weak subjects
    weak_subjects = []
    for exam in all_exams:
        for subj in exam.get('subjects', []):
            if subj.get('weak_subject'):
                weak_subjects.append({'name': subj['name'], 'exam': exam['name']})
    for subj in all_subjects:
        if subj.get('weak_subject'):
            weak_subjects.append({'name': subj['name'], 'exam': 'Independent'})

    return render_template('dashboard.html',
        today=today, habits=habits, logs_today=logs_today,
        habit_completion=habit_completion, max_streak=max_streak,
        today_spend=today_spend, week_spend=week_spend,
        month_spend=month_spend, budget_remaining=budget_remaining, budget=budget,
        goals=goals, goals_completed=goals_completed, goals_pending=goals_pending,
        all_exams=all_exams, all_subjects=all_subjects,
        upcoming_exams=upcoming_exams,
        total_chapters=total_chapters, completed_chapters=completed_chapters,
        revision_pending=revision_pending,
        last_sleep=last_sleep,
        mood_today=mood_today,
        prod_score=prod_score, weekly_scores=weekly_scores,
        thoughts_today=thoughts_today, thoughts_recent=thoughts_recent,
        weak_subjects=weak_subjects,
        currency=data['budget']['currency'],
        settings=data['settings'],
        exercise_done=exercise_done, total_workouts=total_workouts,
        exercise_mins_today=exercise_mins_today, exercise_streak=exercise_streak,
        notes_today=[]
    )

# Redirect removed pages to avoid 404s
@app.route('/planner')
def planner_redirect():
    return redirect(url_for('dashboard'))

@app.route('/focus-timer')
def focus_timer_redirect():
    return redirect(url_for('dashboard'))

@app.route('/reports')
def reports_redirect():
    return redirect(url_for('insights'))

@app.route('/monthly-report')
def monthly_report_redirect():
    return redirect(url_for('insights'))


# ─── Habits ──────────────────────────────────────────────────────────────────

def calc_streak(data, habit_id):
    logs = data.get('habit_logs', {})
    streak = 0
    check_date = date.today()
    while True:
        d = check_date.isoformat()
        if habit_id in logs.get(d, []):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak

@app.route('/habits')
def habits():
    data = load_data()
    today = today_str()
    logs_today = data['habit_logs'].get(today, [])
    habits = data['habits']
    for h in habits:
        h['streak'] = calc_streak(data, h['id'])
        h['done_today'] = h['id'] in logs_today
        # Weekly progress
        week_count = 0
        for i in range(7):
            d = (date.today() - timedelta(days=i)).isoformat()
            if h['id'] in data['habit_logs'].get(d, []):
                week_count += 1
        h['week_count'] = week_count
        h['week_pct'] = round(week_count / 7 * 100)
        # Auto-progress from today sub-tasks
        today_entry_data = next(
            (e for e in data.get('habit_entries',{}).get(str(h['id']),[])
             if e.get('date') == today), None)
        sub_tasks = today_entry_data.get('sub_tasks',[]) if today_entry_data else []
        if sub_tasks:
            done_st = sum(1 for s in sub_tasks if s.get('done'))
            h['subtask_pct'] = round(done_st / len(sub_tasks) * 100)
            h['subtask_done'] = done_st
            h['subtask_total'] = len(sub_tasks)
            h['incomplete_tasks'] = [s['name'] for s in sub_tasks if not s.get('done')]
        else:
            h['subtask_pct'] = None
            h['subtask_done'] = 0
            h['subtask_total'] = 0
            h['incomplete_tasks'] = []
    completion_pct = round(len(logs_today) / len(habits) * 100) if habits else 0
    return render_template('habits.html', habits=habits, today=today,
                           logs_today=logs_today, completion_pct=completion_pct,
                           currency=data['budget']['currency'])

@app.route('/add-habit', methods=['POST'])
def add_habit():
    data = load_data()
    habit = {
        'id': get_id(data['habits']),
        'name': request.form['name'],
        'category': request.form.get('category', 'General'),
        'priority': request.form.get('priority', 'Medium'),
        'frequency': request.form.get('frequency', 'Daily'),
        'notes': request.form.get('notes', ''),
        'created': today_str(),
        'color': request.form.get('color', '#6c63ff')
    }
    data['habits'].append(habit)
    save_data(data)
    return redirect(url_for('habits'))

@app.route('/edit-habit/<int:hid>', methods=['POST'])
def edit_habit(hid):
    data = load_data()
    for h in data['habits']:
        if h['id'] == hid:
            h['name'] = request.form['name']
            h['category'] = request.form.get('category', h.get('category', 'General'))
            h['priority'] = request.form.get('priority', h.get('priority', 'Medium'))
            h['frequency'] = request.form.get('frequency', h.get('frequency', 'Daily'))
            h['notes'] = request.form.get('notes', '')
            h['color'] = request.form.get('color', h.get('color', '#6c63ff'))
            break
    save_data(data)
    return redirect(url_for('habits'))

@app.route('/delete-habit/<int:hid>', methods=['POST'])
def delete_habit(hid):
    data = load_data()
    data['habits'] = [h for h in data['habits'] if h['id'] != hid]
    save_data(data)
    return redirect(url_for('habits'))

@app.route('/toggle-habit/<int:hid>', methods=['POST'])
def toggle_habit(hid):
    data = load_data()
    today = today_str()
    logs = data['habit_logs'].setdefault(today, [])
    if hid in logs:
        logs.remove(hid)
    else:
        logs.append(hid)
    save_data(data)
    return jsonify({'status': 'ok', 'completed': hid in logs, 'count': len(logs)})

@app.route('/habit-history/<int:hid>')
def habit_history(hid):
    data = load_data()
    habit = next((h for h in data['habits'] if h['id'] == hid), None)
    if not habit:
        return redirect(url_for('habits'))
    history = []
    for i in range(30):
        d = (date.today() - timedelta(days=i)).isoformat()
        done = hid in data['habit_logs'].get(d, [])
        history.append({'date': d, 'done': done})
    return render_template('habit_history.html', habit=habit, history=history)

# ─── Habit Detail Page ────────────────────────────────────────────────────────

@app.route('/habit/<int:hid>')
def habit_detail(hid):
    data = load_data()
    habit = next((h for h in data['habits'] if h['id'] == hid), None)
    if not habit:
        return redirect(url_for('habits'))
    today = today_str()
    # Get entries for this habit
    entries_all = data.get('habit_entries', {}).get(str(hid), [])
    # Get today's entry
    today_entry = next((e for e in entries_all if e.get('date') == today), None)
    if not today_entry:
        today_entry = {'date': today, 'sub_tasks': [], 'time_slots': [], 'notes': ''}
    # Calculate total hours today
    total_hours = 0.0
    for ts in today_entry.get('time_slots', []):
        total_hours += ts.get('duration_hours', 0)
    # All completed sub_tasks today
    completed_tasks = [st for st in today_entry.get('sub_tasks', []) if st.get('done')]
    # Check auto-completion
    all_sub = today_entry.get('sub_tasks', [])
    if all_sub and all(st.get('done') for st in all_sub):
        logs = data['habit_logs'].setdefault(today, [])
        if hid not in logs:
            logs.append(hid)
            save_data(data)
    streak = calc_streak(data, hid)
    # 30-day history
    history = []
    for i in range(30):
        d = (date.today() - timedelta(days=i)).isoformat()
        done = hid in data['habit_logs'].get(d, [])
        day_entry = next((e for e in entries_all if e.get('date') == d), None)
        hours = sum(ts.get('duration_hours', 0) for ts in (day_entry or {}).get('time_slots', []))
        history.append({'date': d, 'done': done, 'hours': round(hours, 1)})
    return render_template('habit_detail.html', habit=habit, today=today,
                           today_entry=today_entry, total_hours=round(total_hours, 2),
                           completed_tasks=completed_tasks, streak=streak, history=history)

@app.route('/habit/<int:hid>/add-subtask', methods=['POST'])
def add_subtask(hid):
    data = load_data()
    today = today_str()
    entries = data.setdefault('habit_entries', {}).setdefault(str(hid), [])
    entry = next((e for e in entries if e.get('date') == today), None)
    if not entry:
        entry = {'date': today, 'sub_tasks': [], 'time_slots': [], 'notes': ''}
        entries.append(entry)
    st = {
        'id': len(entry['sub_tasks']) + 1,
        'name': request.form['name'],
        'type': request.form.get('type', 'general'),
        'quantity': request.form.get('quantity', ''),
        'unit': request.form.get('unit', ''),
        'notes': request.form.get('notes', ''),
        'done': False
    }
    entry['sub_tasks'].append(st)
    save_data(data)
    return redirect(url_for('habit_detail', hid=hid))

@app.route('/habit/<int:hid>/toggle-subtask/<int:stid>', methods=['POST'])
def toggle_subtask(hid, stid):
    data = load_data()
    today = today_str()
    entries = data.get('habit_entries', {}).get(str(hid), [])
    entry = next((e for e in entries if e.get('date') == today), None)
    if entry:
        for st in entry.get('sub_tasks', []):
            if st['id'] == stid:
                st['done'] = not st.get('done', False)
                break
        # Auto complete habit if all sub-tasks done
        all_tasks = entry.get('sub_tasks', [])
        if all_tasks and all(t.get('done') for t in all_tasks):
            logs = data['habit_logs'].setdefault(today, [])
            if hid not in logs:
                logs.append(hid)
        save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/habit/<int:hid>/delete-subtask/<int:stid>', methods=['POST'])
def delete_subtask(hid, stid):
    data = load_data()
    today = today_str()
    entries = data.get('habit_entries', {}).get(str(hid), [])
    entry = next((e for e in entries if e.get('date') == today), None)
    if entry:
        entry['sub_tasks'] = [st for st in entry.get('sub_tasks', []) if st['id'] != stid]
        save_data(data)
    return redirect(url_for('habit_detail', hid=hid))

@app.route('/habit/<int:hid>/add-timeslot', methods=['POST'])
def add_timeslot(hid):
    data = load_data()
    today = today_str()
    entries = data.setdefault('habit_entries', {}).setdefault(str(hid), [])
    entry = next((e for e in entries if e.get('date') == today), None)
    if not entry:
        entry = {'date': today, 'sub_tasks': [], 'time_slots': [], 'notes': ''}
        entries.append(entry)
    start = request.form.get('start_time', '00:00')
    end   = request.form.get('end_time', '00:00')
    try:
        s = datetime.strptime(start, '%H:%M')
        e_time = datetime.strptime(end, '%H:%M')
        if e_time < s:
            e_time = e_time.replace(day=e_time.day + 1)
        hours = round((e_time - s).seconds / 3600, 2)
    except:
        hours = 0
    ts = {
        'id': len(entry['time_slots']) + 1,
        'start': start, 'end': end,
        'duration_hours': hours,
        'label': request.form.get('label', '')
    }
    entry['time_slots'].append(ts)
    save_data(data)
    return redirect(url_for('habit_detail', hid=hid))

@app.route('/habit/<int:hid>/delete-timeslot/<int:tsid>', methods=['POST'])
def delete_timeslot(hid, tsid):
    data = load_data()
    today = today_str()
    entries = data.get('habit_entries', {}).get(str(hid), [])
    entry = next((e for e in entries if e.get('date') == today), None)
    if entry:
        entry['time_slots'] = [ts for ts in entry.get('time_slots', []) if ts['id'] != tsid]
        save_data(data)
    return redirect(url_for('habit_detail', hid=hid))

# ─── API: Search ──────────────────────────────────────────────────────────────

@app.route('/api/search')
def api_search():
    data = load_data()
    q = request.args.get('q', '').lower().strip()
    section = request.args.get('section', 'all')
    results = []
    if not q:
        return jsonify([])
    if section in ('all', 'habits'):
        for h in data['habits']:
            if q in h['name'].lower() or q in h.get('category','').lower():
                results.append({'type':'habit','id':h['id'],'title':h['name'],'sub':h.get('category',''),'url':f"/habit/{h['id']}"})
    if section in ('all', 'expenses'):
        for e in data['expenses']:
            if q in e.get('description','').lower() or q in e.get('category','').lower():
                results.append({'type':'expense','id':e['id'],'title':e.get('description') or e['category'],'sub':f"{e['date']} · {e['category']}",'url':'/spending'})
    if section in ('all', 'exams'):
        for ex in data['exams']:
            if q in ex['name'].lower():
                results.append({'type':'exam','id':ex['id'],'title':ex['name'],'sub':ex.get('type',''),'url':f"/exam/{ex['id']}"})
            for s in ex.get('subjects',[]):
                if q in s['name'].lower():
                    results.append({'type':'subject','id':s['id'],'title':s['name'],'sub':f"in {ex['name']}",'url':f"/subject/{s['id']}"})
    if section in ('all', 'subjects'):
        for s in data['subjects']:
            if q in s['name'].lower():
                results.append({'type':'subject','id':s['id'],'title':s['name'],'sub':s.get('category',''),'url':f"/subject/{s['id']}"})
    if section in ('all', 'goals'):
        for g in data['goals']:
            if q in g['title'].lower() or q in g.get('description','').lower():
                results.append({'type':'goal','id':g['id'],'title':g['title'],'sub':g['status'],'url':'/goals'})
    if section in ('all', 'notes'):
        for d_str, notes in data.get('notes',{}).items():
            for n in notes:
                if q in n.get('text','').lower():
                    results.append({'type':'note','id':n.get('id',0),'title':n['text'][:60],'sub':d_str,'url':f"/date-details/{d_str}"})
    return jsonify(results[:20])

# ─── Spending ────────────────────────────────────────────────────────────────

@app.route('/spending')
def spending():
    data = load_data()
    today = today_str()
    month_start = date.today().replace(day=1).isoformat()
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    expenses = sorted(data['expenses'], key=lambda x: x['date'], reverse=True)
    today_exp = [e for e in expenses if e['date'] == today]
    week_exp = [e for e in expenses if e['date'] >= week_start]
    month_exp = [e for e in expenses if e['date'] >= month_start]

    today_total = sum(e['amount'] for e in today_exp)
    week_total = sum(e['amount'] for e in week_exp)
    month_total = sum(e['amount'] for e in month_exp)
    budget = data['budget']['monthly']
    budget_pct = round(month_total / budget * 100) if budget else 0

    # Category breakdown
    cat_totals = {}
    for e in month_exp:
        cat_totals[e['category']] = cat_totals.get(e['category'], 0) + e['amount']

    # Daily trend last 7 days
    daily_trend = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        amt = sum(e['amount'] for e in expenses if e['date'] == d)
        daily_trend.append({'date': d, 'amount': amt})

    return render_template('spending.html',
        expenses=expenses[:50], today_exp=today_exp,
        today_total=today_total, week_total=week_total,
        month_total=month_total, budget=budget, budget_pct=budget_pct,
        budget_remaining=budget - month_total,
        cat_totals=cat_totals, daily_trend=daily_trend,
        currency=data['budget']['currency']
    )

@app.route('/add-expense', methods=['POST'])
def add_expense():
    data = load_data()
    expense = {
        'id': get_id(data['expenses']),
        'amount': float(request.form['amount']),
        'category': request.form['category'],
        'description': request.form.get('description', ''),
        'date': request.form.get('date', today_str()),
        'payment_method': request.form.get('payment_method', 'Cash'),
        'tag': request.form.get('tag', ''),
        'created': today_str()
    }
    data['expenses'].append(expense)
    save_data(data)
    return redirect(url_for('spending'))

@app.route('/edit-expense/<int:eid>', methods=['POST'])
def edit_expense(eid):
    data = load_data()
    for e in data['expenses']:
        if e['id'] == eid:
            e['amount'] = float(request.form['amount'])
            e['category'] = request.form['category']
            e['description'] = request.form.get('description', '')
            e['date'] = request.form.get('date', e['date'])
            e['payment_method'] = request.form.get('payment_method', e.get('payment_method', 'Cash'))
            e['tag'] = request.form.get('tag', '')
            break
    save_data(data)
    return redirect(url_for('spending'))

@app.route('/delete-expense/<int:eid>', methods=['POST'])
def delete_expense(eid):
    data = load_data()
    data['expenses'] = [e for e in data['expenses'] if e['id'] != eid]
    save_data(data)
    return redirect(url_for('spending'))

@app.route('/set-budget', methods=['POST'])
def set_budget():
    data = load_data()
    data['budget']['monthly'] = float(request.form['monthly'])
    data['budget']['currency'] = request.form.get('currency', '₹')
    save_data(data)
    return redirect(url_for('spending'))

# ─── Study ───────────────────────────────────────────────────────────────────

@app.route('/study')
def study():
    data = load_data()
    today = today_str()
    exams = data['exams']
    subjects = data['subjects']

    # Compute progress for exams
    for exam in exams:
        total = sum(len(s.get('chapters', [])) for s in exam.get('subjects', []))
        done = sum(1 for s in exam.get('subjects', []) for c in s.get('chapters', []) if c.get('status') == 'Completed')
        exam['progress'] = round(done / total * 100) if total else 0
        exam['days_left'] = None
        if exam.get('date'):
            try:
                delta = (datetime.strptime(exam['date'], '%Y-%m-%d').date() - date.today()).days
                exam['days_left'] = delta
            except Exception: pass
        # Per-subject auto-progress
        for s in exam.get('subjects', []):
            st = len(s.get('chapters', []))
            sd = sum(1 for c in s.get('chapters', []) if c.get('status') == 'Completed')
            s['progress'] = round(sd / st * 100) if st else 0
            s['completion_done'] = sd
            s['completion_total'] = st
            s['auto_weak'] = (st > 0 and s['progress'] < 40)

    # Compute progress for independent subjects (auto from chapters)
    for subj in subjects:
        total = len(subj.get('chapters', []))
        done = sum(1 for c in subj.get('chapters', []) if c.get('status') == 'Completed')
        auto_pct = round(done / total * 100) if total else 0
        subj['progress'] = auto_pct
        subj['completion_done'] = done
        subj['completion_total'] = total
        # Weak subject: <40% completion with chapters added
        if total > 0 and auto_pct < 40:
            subj['auto_weak'] = True
        else:
            subj['auto_weak'] = False

    upcoming_exams = sorted([e for e in exams if e.get('date', '') >= today], key=lambda x: x['date'])

    total_chapters = sum(len(s.get('chapters', [])) for e in exams for s in e.get('subjects', []))
    total_chapters += sum(len(s.get('chapters', [])) for s in subjects)
    completed_chapters = sum(1 for e in exams for s in e.get('subjects', []) for c in s.get('chapters', []) if c.get('status') == 'Completed')
    completed_chapters += sum(1 for s in subjects for c in s.get('chapters', []) if c.get('status') == 'Completed')
    revision_pending = sum(1 for e in exams for s in e.get('subjects', []) for c in s.get('chapters', []) if c.get('status') == 'Revision Pending')
    revision_pending += sum(1 for s in subjects for c in s.get('chapters', []) if c.get('status') == 'Revision Pending')

    return render_template('study.html',
        exams=exams, subjects=subjects,
        upcoming_exams=upcoming_exams,
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        revision_pending=revision_pending,
        today=today
    )

@app.route('/add-exam', methods=['POST'])
def add_exam():
    data = load_data()
    exam = {
        'id': get_id(data['exams']),
        'name': request.form['name'],
        'date': request.form.get('date', ''),
        'type': request.form.get('type', 'General'),
        'priority': request.form.get('priority', 'Medium'),
        'status': request.form.get('status', 'Not Started'),
        'notes': request.form.get('notes', ''),
        'syllabus': request.form.get('syllabus', ''),
        'created': today_str(),
        'subjects': []
    }
    data['exams'].append(exam)
    save_data(data)
    return redirect(url_for('study'))

@app.route('/edit-exam/<int:eid>', methods=['POST'])
def edit_exam(eid):
    data = load_data()
    for e in data['exams']:
        if e['id'] == eid:
            e['name'] = request.form['name']
            e['date'] = request.form.get('date', '')
            e['type'] = request.form.get('type', e.get('type', 'General'))
            e['priority'] = request.form.get('priority', e.get('priority', 'Medium'))
            e['status'] = request.form.get('status', e.get('status', 'Not Started'))
            e['notes'] = request.form.get('notes', '')
            e['syllabus'] = request.form.get('syllabus', e.get('syllabus', ''))
            break
    save_data(data)
    return redirect(url_for('study'))

@app.route('/delete-exam/<int:eid>', methods=['POST'])
def delete_exam(eid):
    data = load_data()
    data['exams'] = [e for e in data['exams'] if e['id'] != eid]
    save_data(data)
    return redirect(url_for('study'))

@app.route('/exam/<int:eid>')
def exam_detail(eid):
    data = load_data()
    exam = next((e for e in data['exams'] if e['id'] == eid), None)
    if not exam:
        return redirect(url_for('study'))
    for subj in exam.get('subjects', []):
        total = len(subj.get('chapters', []))
        done = sum(1 for c in subj.get('chapters', []) if c.get('status') == 'Completed')
        subj['progress'] = round(done / total * 100) if total else 0
    days_left = None
    if exam.get('date'):
        delta = (datetime.strptime(exam['date'], '%Y-%m-%d').date() - date.today()).days
        days_left = delta
    return render_template('exam_detail.html', exam=exam, days_left=days_left)

@app.route('/add-subject/<int:eid>', methods=['POST'])
def add_subject(eid):
    data = load_data()
    for e in data['exams']:
        if e['id'] == eid:
            subj = {
                'id': get_id([s for ex in data['exams'] for s in ex.get('subjects', [])] + data['subjects']),
                'name': request.form['name'],
                'priority': request.form.get('priority', 'Medium'),
                'status': request.form.get('status', 'Not Started'),
                'notes': request.form.get('notes', ''),
                'weak_subject': request.form.get('weak_subject') == 'on',
                'start_date': request.form.get('start_date', ''),
                'reference_books': request.form.get('reference_books', ''),
                'created': today_str(),
                'chapters': [],
                'revisions': []
            }
            e['subjects'].append(subj)
            break
    save_data(data)
    return redirect(url_for('exam_detail', eid=eid))

@app.route('/edit-subject/<int:eid>/<int:sid>', methods=['POST'])
def edit_subject(eid, sid):
    data = load_data()
    for e in data['exams']:
        if e['id'] == eid:
            for s in e['subjects']:
                if s['id'] == sid:
                    s['name'] = request.form['name']
                    s['priority'] = request.form.get('priority', s.get('priority', 'Medium'))
                    s['status'] = request.form.get('status', s.get('status', 'Not Started'))
                    s['notes'] = request.form.get('notes', '')
                    s['weak_subject'] = request.form.get('weak_subject') == 'on'
                    s['reference_books'] = request.form.get('reference_books', s.get('reference_books', ''))
                    break
    save_data(data)
    return redirect(url_for('exam_detail', eid=eid))

@app.route('/delete-subject/<int:eid>/<int:sid>', methods=['POST'])
def delete_subject(eid, sid):
    data = load_data()
    for e in data['exams']:
        if e['id'] == eid:
            e['subjects'] = [s for s in e['subjects'] if s['id'] != sid]
            break
    save_data(data)
    return redirect(url_for('exam_detail', eid=eid))

@app.route('/subject/<int:sid>')
def subject_detail(sid):
    data = load_data()
    # Find in exams
    exam = None
    subj = None
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                exam = e
                subj = s
                break
    # Find in independent
    if not subj:
        subj = next((s for s in data['subjects'] if s['id'] == sid), None)
    if not subj:
        return redirect(url_for('study'))
    total = len(subj.get('chapters', []))
    done = sum(1 for c in subj.get('chapters', []) if c.get('status') == 'Completed')
    subj['progress'] = round(done / total * 100) if total else 0
    return render_template('subject_detail.html', subj=subj, exam=exam, today=today_str())

@app.route('/add-chapter/<int:sid>', methods=['POST'])
def add_chapter(sid):
    data = load_data()
    chapter = {
        'id': get_id([c for e in data['exams'] for s in e.get('subjects',[]) for c in s.get('chapters',[])] + [c for s in data['subjects'] for c in s.get('chapters',[])]),
        'name': request.form['name'],
        'number': request.form.get('number', ''),
        'status': 'Not Started',        # ALWAYS Not Started on creation (Part E)
        'revision_required': request.form.get('revision_required') == 'on',
        'important': request.form.get('important') == 'on',
        'priority': request.form.get('priority', 'Medium'),
        'notes': request.form.get('notes', ''),
        'difficulty': request.form.get('difficulty', 'Medium'),
        'estimated_hours': request.form.get('estimated_hours', ''),
        'actual_hours': '',
        'start_date': None,             # NEVER auto-set on creation (Part E)
        'completion_date': '',
        'study_sessions': [],           # Part F
        'chapter_revisions': [],        # Part G
        'created': today_str()
    }
    # Search in exams
    found = False
    eid = None
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                s['chapters'].append(chapter)
                eid = e['id']
                found = True
                break
    if not found:
        for s in data['subjects']:
            if s['id'] == sid:
                s['chapters'].append(chapter)
                break
    save_data(data)
    return redirect(url_for('subject_detail', sid=sid))

@app.route('/edit-chapter/<int:sid>/<int:cid>', methods=['POST'])
def edit_chapter(sid, cid):
    data = load_data()
    def update_chapter(chapters):
        for c in chapters:
            if c['id'] == cid:
                c['name'] = request.form['name']
                c['number'] = request.form.get('number', c.get('number', ''))
                old_status = c.get('status', 'Not Started')
                c['status'] = request.form.get('status', old_status)
                if c['status'] == 'Completed' and old_status != 'Completed':
                    c['completion_date'] = today_str()
                elif c['status'] != 'Completed':
                    c['completion_date'] = ''
                c['revision_required'] = request.form.get('revision_required') == 'on'
                c['important'] = request.form.get('important') == 'on'
                c['priority'] = request.form.get('priority', c.get('priority', 'Medium'))
                c['notes'] = request.form.get('notes', '')
                c['difficulty'] = request.form.get('difficulty', c.get('difficulty', 'Medium'))
                c['estimated_hours'] = request.form.get('estimated_hours', c.get('estimated_hours', ''))
                c['actual_hours'] = request.form.get('actual_hours', c.get('actual_hours', ''))
                c['start_date'] = request.form.get('start_date', c.get('start_date', ''))
                return True
        return False
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                update_chapter(s.get('chapters', []))
    for s in data['subjects']:
        if s['id'] == sid:
            update_chapter(s.get('chapters', []))
    save_data(data)
    return redirect(url_for('subject_detail', sid=sid))

@app.route('/toggle-chapter/<int:sid>/<int:cid>', methods=['POST'])
def toggle_chapter(sid, cid):
    data = load_data()
    new_status = request.form.get('status', 'Completed')
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                for c in s.get('chapters', []):
                    if c['id'] == cid:
                        c['status'] = new_status
                        if new_status == 'Completed':
                            c['completion_date'] = today_str()
                        save_data(data)
                        return jsonify({'status': 'ok'})
    for s in data['subjects']:
        if s['id'] == sid:
            for c in s.get('chapters', []):
                if c['id'] == cid:
                    c['status'] = new_status
                    if new_status == 'Completed':
                        c['completion_date'] = today_str()
                    save_data(data)
                    return jsonify({'status': 'ok'})
    return jsonify({'status': 'error'})

@app.route('/delete-chapter/<int:sid>/<int:cid>', methods=['POST'])
def delete_chapter(sid, cid):
    data = load_data()
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                s['chapters'] = [c for c in s.get('chapters', []) if c['id'] != cid]
    for s in data['subjects']:
        if s['id'] == sid:
            s['chapters'] = [c for c in s.get('chapters', []) if c['id'] != cid]
    save_data(data)
    return redirect(url_for('subject_detail', sid=sid))

# ─── Start Chapter (Part E) ───────────────────────────────────────────────────

@app.route('/start-chapter/<int:sid>/<int:cid>', methods=['POST'])
def start_chapter(sid, cid):
    """Set start_date = today and status = In Progress. Only called by user clicking Start."""
    data = load_data()
    def _start(chapters):
        for c in chapters:
            if c['id'] == cid:
                if not c.get('start_date'):      # only set once
                    c['start_date'] = today_str()
                c['status'] = 'In Progress'
                return True
        return False
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid and _start(s.get('chapters', [])):
                save_data(data)
                return jsonify({'status': 'ok', 'start_date': today_str()})
    for s in data['subjects']:
        if s['id'] == sid and _start(s.get('chapters', [])):
            save_data(data)
            return jsonify({'status': 'ok', 'start_date': today_str()})
    return jsonify({'status': 'error'})

# ─── Study Sessions (Part F) ─────────────────────────────────────────────────

@app.route('/add-study-session/<int:sid>/<int:cid>', methods=['POST'])
def add_study_session(sid, cid):
    """Add a manual study session to a chapter. Updates actual_hours."""
    data = load_data()
    # Calculate duration
    start_t = request.form.get('start_time', '')
    end_t   = request.form.get('end_time', '')
    dur_h   = request.form.get('duration_hours', '')
    if start_t and end_t:
        try:
            s_dt = datetime.strptime(start_t, '%H:%M')
            e_dt = datetime.strptime(end_t,   '%H:%M')
            if e_dt <= s_dt:
                e_dt = e_dt.replace(day=e_dt.day + 1)
            duration = round((e_dt - s_dt).total_seconds() / 3600, 2)
        except:
            duration = float(dur_h) if dur_h else 0
    else:
        duration = float(dur_h) if dur_h else 0

    session = {
        'id': int(datetime.now(_IST).timestamp() * 1000),
        'date': request.form.get('date', '') or today_str(),
        'start_time': start_t,
        'end_time':   end_t,
        'duration':   duration,
        'notes':      request.form.get('notes', '')
    }

    def _add_session(chapters):
        for c in chapters:
            if c['id'] == cid:
                c.setdefault('study_sessions', []).append(session)
                # Sync actual_hours = sum of all sessions
                total = sum(ss.get('duration', 0) for ss in c['study_sessions'])
                c['actual_hours'] = round(total, 2)
                return True
        return False

    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid and _add_session(s.get('chapters', [])):
                save_data(data)
                return redirect(url_for('subject_detail', sid=sid))
    for s in data['subjects']:
        if s['id'] == sid and _add_session(s.get('chapters', [])):
            save_data(data)
            return redirect(url_for('subject_detail', sid=sid))
    return redirect(url_for('subject_detail', sid=sid))

@app.route('/delete-study-session/<int:sid>/<int:cid>/<int:sess_id>', methods=['POST'])
def delete_study_session(sid, cid, sess_id):
    data = load_data()
    def _del(chapters):
        for c in chapters:
            if c['id'] == cid:
                c['study_sessions'] = [ss for ss in c.get('study_sessions', []) if ss.get('id') != sess_id]
                c['actual_hours'] = round(sum(ss.get('duration', 0) for ss in c['study_sessions']), 2)
                return True
        return False
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid: _del(s.get('chapters', []))
    for s in data['subjects']:
        if s['id'] == sid: _del(s.get('chapters', []))
    save_data(data)
    return redirect(url_for('subject_detail', sid=sid))

# ─── Chapter Revisions (Part G) ──────────────────────────────────────────────

@app.route('/add-chapter-revision/<int:sid>/<int:cid>', methods=['POST'])
def add_chapter_revision(sid, cid):
    """Add a revision entry to a specific chapter."""
    data = load_data()
    def _add_rev(chapters):
        for c in chapters:
            if c['id'] == cid:
                revs = c.setdefault('chapter_revisions', [])
                rev = {
                    'id': len(revs) + 1,
                    'number': len(revs) + 1,
                    'date': request.form.get('date', '') or today_str(),
                    'notes': request.form.get('notes', ''),
                    'confidence': request.form.get('confidence', 'Medium')
                }
                revs.append(rev)
                return True
        return False
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid and _add_rev(s.get('chapters', [])):
                save_data(data)
                return redirect(url_for('subject_detail', sid=sid))
    for s in data['subjects']:
        if s['id'] == sid and _add_rev(s.get('chapters', [])):
            save_data(data)
            return redirect(url_for('subject_detail', sid=sid))
    return redirect(url_for('subject_detail', sid=sid))

# Independent subjects
@app.route('/add-independent-subject', methods=['POST'])
def add_independent_subject():
    data = load_data()
    all_ids = [s['id'] for s in data['subjects']] + [s['id'] for e in data['exams'] for s in e.get('subjects',[])]
    subj = {
        'id': (max(all_ids) + 1) if all_ids else 1,
        'name': request.form['name'],
        'category': request.form.get('category', 'Personal'),
        'priority': request.form.get('priority', 'Medium'),
        'status': request.form.get('status', 'Not Started'),
        'notes': request.form.get('notes', ''),
        'weak_subject': request.form.get('weak_subject') == 'on',
        'start_date': request.form.get('start_date', ''),
        'resource_links': request.form.get('resource_links', ''),
        'created': today_str(),
        'chapters': [],
        'revisions': [],
        'manual_progress': 0
    }
    data['subjects'].append(subj)
    save_data(data)
    return redirect(url_for('study'))

@app.route('/edit-independent-subject/<int:sid>', methods=['POST'])
def edit_independent_subject(sid):
    data = load_data()
    for s in data['subjects']:
        if s['id'] == sid:
            s['name'] = request.form['name']
            s['category'] = request.form.get('category', s.get('category', 'Personal'))
            s['priority'] = request.form.get('priority', s.get('priority', 'Medium'))
            s['status'] = request.form.get('status', s.get('status', 'Not Started'))
            s['notes'] = request.form.get('notes', '')
            s['weak_subject'] = request.form.get('weak_subject') == 'on'
            s['resource_links'] = request.form.get('resource_links', s.get('resource_links', ''))
            break
    save_data(data)
    return redirect(url_for('study'))

@app.route('/delete-independent-subject/<int:sid>', methods=['POST'])
def delete_independent_subject(sid):
    data = load_data()
    data['subjects'] = [s for s in data['subjects'] if s['id'] != sid]
    save_data(data)
    return redirect(url_for('study'))

@app.route('/add-revision/<int:sid>', methods=['POST'])
def add_revision(sid):
    data = load_data()
    revision = {
        'id': len(data.get('revisions', [])) + 1,
        'date': today_str(),
        'type': request.form.get('type', 'Revision 1'),
        'notes': request.form.get('notes', ''),
        'confidence': request.form.get('confidence', 'Medium')
    }
    for e in data['exams']:
        for s in e.get('subjects', []):
            if s['id'] == sid:
                s.setdefault('revisions', []).append(revision)
                save_data(data)
                return redirect(url_for('subject_detail', sid=sid))
    for s in data['subjects']:
        if s['id'] == sid:
            s.setdefault('revisions', []).append(revision)
    save_data(data)
    return redirect(url_for('subject_detail', sid=sid))

# ─── Calendar ────────────────────────────────────────────────────────────────

@app.route('/calendar')
def calendar_view():
    data = load_data()
    today = today_str()
    # Build calendar data for current month
    today_date = date.today()
    return render_template('calendar.html', today=today,
                           today_date=today_date, data=data)

@app.route('/date-details/<date_str>')
def date_details(date_str):
    data = load_data()
    logs = data['habit_logs'].get(date_str, [])
    habits = data['habits']
    done_habits = [h for h in habits if h['id'] in logs]
    missed_habits = [h for h in habits if h['id'] not in logs]
    expenses = [e for e in data['expenses'] if e['date'] == date_str]
    total_spend = sum(e['amount'] for e in expenses)
    notes = data['notes'].get(date_str, [])
    thoughts_date = [t for t in data.get('thoughts', []) if t.get('date') == date_str]
    tasks = [t for t in data['tasks'] if t.get('date') == date_str]
    sleep = next((s for s in reversed(data['sleep_logs']) if s.get('date') == date_str), None)
    focus = [f for f in data.get('focus_sessions', []) if f.get('date') == date_str]
    focus_mins = sum(f.get('duration', 0) for f in focus)
    mood = data.get('mood_logs', {}).get(date_str)
    journal = data.get('journal_entries', {}).get(date_str, '')
    prod_score = calc_productivity_score(data, date_str)  # may be None

    # Study activity
    study_activity = []
    for exam in data['exams']:
        for subj in exam.get('subjects', []):
            for ch in subj.get('chapters', []):
                if ch.get('completion_date') == date_str or ch.get('start_date') == date_str:
                    study_activity.append({'exam': exam['name'], 'subject': subj['name'], 'chapter': ch['name'], 'status': ch['status']})
    for subj in data['subjects']:
        for ch in subj.get('chapters', []):
            if ch.get('completion_date') == date_str or ch.get('start_date') == date_str:
                study_activity.append({'exam': 'Independent', 'subject': subj['name'], 'chapter': ch['name'], 'status': ch['status']})

    # Exercise data for this date
    workout_logs_day = data.get('workout_logs', {}).get(date_str, [])
    workouts_map = {w['id']: w for w in data.get('workouts', [])}
    exercise_entries = [{'workout': workouts_map.get(l['workout_id'], {'name': 'Unknown'}),
                         'log': l} for l in workout_logs_day]
    # Focus sessions for this date
    focus_sessions_day = [s for s in data.get('focus_timer_sessions', [])
                          if s.get('date') == date_str]

    return render_template('date_details.html',
        date_str=date_str, done_habits=done_habits, missed_habits=missed_habits,
        expenses=expenses, total_spend=total_spend, notes=notes,
        tasks=tasks, sleep=sleep, focus_mins=focus_mins, mood=mood,
        journal=journal, prod_score=prod_score,
        study_activity=study_activity, thoughts_date=thoughts_date, currency=data['budget']['currency'],
        exercise_entries=exercise_entries, focus_sessions_day=focus_sessions_day
    )

@app.route('/save-journal', methods=['POST'])
def save_journal():
    data = load_data()
    date_str = request.form.get('date', today_str())
    data.setdefault('journal_entries', {})[date_str] = request.form.get('journal', '')
    save_data(data)
    return redirect(url_for('date_details', date_str=date_str))

@app.route('/log-mood', methods=['POST'])
def log_mood():
    data = load_data()
    date_str = request.form.get('date', today_str())
    data.setdefault('mood_logs', {})[date_str] = request.form.get('mood', '😐')
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/log-water', methods=['POST'])
def log_water():
    data = load_data()
    date_str = request.form.get('date', today_str())
    glasses = int(request.form.get('glasses', 0))
    data.setdefault('water_logs', {})[date_str] = glasses
    save_data(data)
    return jsonify({'status': 'ok', 'glasses': glasses})

# ─── Notes ───────────────────────────────────────────────────────────────────

@app.route('/notes')
def notes():
    data = load_data()
    all_notes = []
    for d, note_list in data.get('notes', {}).items():
        for n in note_list:
            n['date'] = d
            all_notes.append(n)
    all_notes.sort(key=lambda x: x['date'], reverse=True)
    return render_template('notes.html', all_notes=all_notes, today=today_str())

@app.route('/save-note', methods=['POST'])
def save_note():
    data = load_data()
    date_str = request.form.get('date', today_str())
    note = {
        'id': sum(len(v) for v in data.get('notes', {}).values()) + 1,
        'text': request.form['text'],
        'category': request.form.get('category', 'General'),
        'pinned': request.form.get('pinned') == 'on',
        'created': datetime.now(_IST).isoformat()
    }
    data.setdefault('notes', {}).setdefault(date_str, []).append(note)
    save_data(data)
    return redirect(request.referrer or url_for('notes'))

@app.route('/delete-note/<date_str>/<int:nid>', methods=['POST'])
def delete_note(date_str, nid):
    data = load_data()
    if date_str in data.get('notes', {}):
        data['notes'][date_str] = [n for n in data['notes'][date_str] if n.get('id') != nid]
    save_data(data)
    return redirect(request.referrer or url_for('notes'))


# ─── Thoughts ────────────────────────────────────────────────────────────────

@app.route('/thoughts')
def thoughts():
    data = load_data()
    all_thoughts = data.get('thoughts', [])
    # Sort by created_at desc
    all_thoughts = sorted(all_thoughts, key=lambda x: x.get('created_at',''), reverse=True)
    # Filter params
    type_filter = request.args.get('type', '')
    mood_filter = request.args.get('mood', '')
    date_filter = request.args.get('date', '')
    search_q    = request.args.get('q', '')
    filtered = all_thoughts
    if type_filter:
        filtered = [t for t in filtered if t.get('type') == type_filter]
    if mood_filter:
        filtered = [t for t in filtered if t.get('mood') == mood_filter]
    if date_filter:
        filtered = [t for t in filtered if t.get('date') == date_filter]
    if search_q:
        sq = search_q.lower()
        filtered = [t for t in filtered if sq in t.get('title','').lower() or sq in t.get('content','').lower()]
    pinned = [t for t in filtered if t.get('pinned')]
    unpinned = [t for t in filtered if not t.get('pinned')]
    all_tags = sorted(set(tag for t in all_thoughts for tag in t.get('tags', [])))
    return render_template('thoughts.html', thoughts=filtered, pinned=pinned, unpinned=unpinned,
                           all_tags=all_tags, today=today_str(),
                           type_filter=type_filter, mood_filter=mood_filter,
                           date_filter=date_filter, search_q=search_q,
                           all_thoughts_count=len(all_thoughts))

@app.route('/add-thought', methods=['POST'])
def add_thought():
    data = load_data()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    thought = {
        'id': (max((t['id'] for t in data.get('thoughts', [])), default=0) + 1),
        'title': request.form.get('title', '').strip() or 'Untitled',
        'content': request.form.get('content', ''),
        'type': request.form.get('type', 'Thought'),
        'mood': request.form.get('mood', ''),
        'tags': tags,
        'date': request.form.get('date', today_str()),
        'created_at': datetime.now(_IST).isoformat(),
        'pinned': request.form.get('pinned') == 'on',
        'favorite': False
    }
    data.setdefault('thoughts', []).append(thought)
    save_data(data)
    return redirect(request.referrer or url_for('thoughts'))

@app.route('/edit-thought/<int:tid>', methods=['POST'])
def edit_thought(tid):
    data = load_data()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    for t in data.get('thoughts', []):
        if t['id'] == tid:
            t['title']   = request.form.get('title', t['title'])
            t['content'] = request.form.get('content', t['content'])
            t['type']    = request.form.get('type', t['type'])
            t['mood']    = request.form.get('mood', t.get('mood',''))
            t['tags']    = tags
            t['date']    = request.form.get('date', t['date'])
            t['pinned']  = request.form.get('pinned') == 'on'
            break
    save_data(data)
    return redirect(url_for('thoughts'))

@app.route('/delete-thought/<int:tid>', methods=['POST'])
def delete_thought(tid):
    data = load_data()
    data['thoughts'] = [t for t in data.get('thoughts', []) if t['id'] != tid]
    save_data(data)
    return redirect(request.referrer or url_for('thoughts'))

@app.route('/toggle-favorite-thought/<int:tid>', methods=['POST'])
def toggle_favorite_thought(tid):
    data = load_data()
    for t in data.get('thoughts', []):
        if t['id'] == tid:
            t['favorite'] = not t.get('favorite', False)
            break
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/toggle-pin-thought/<int:tid>', methods=['POST'])
def toggle_pin_thought(tid):
    data = load_data()
    for t in data.get('thoughts', []):
        if t['id'] == tid:
            t['pinned'] = not t.get('pinned', False)
            break
    save_data(data)
    return jsonify({'status': 'ok'})

# ─── Goals ───────────────────────────────────────────────────────────────────

@app.route('/add-goal', methods=['POST'])
def add_goal():
    data = load_data()
    goal = {
        'id': get_id(data['goals']),
        'title': request.form['title'],
        'description': request.form.get('description', ''),
        'target_year': request.form.get('target_year', ''),
        'target_date': request.form.get('target_date', ''),
        'motivation': request.form.get('motivation', ''),
        'status': request.form.get('status', 'Pending'),
        'progress': int(request.form.get('progress', 0)),
        'category': request.form.get('category', 'Personal'),
        'created': today_str(),
        'milestones': []
    }
    data['goals'].append(goal)
    save_data(data)
    return redirect(url_for('goals'))

@app.route('/edit-goal/<int:gid>', methods=['POST'])
def edit_goal(gid):
    data = load_data()
    for g in data['goals']:
        if g['id'] == gid:
            g['title'] = request.form['title']
            g['description'] = request.form.get('description', '')
            g['target_year'] = request.form.get('target_year', '')
            g['target_date'] = request.form.get('target_date', '')
            g['motivation'] = request.form.get('motivation', '')
            g['status'] = request.form.get('status', g['status'])
            g['progress'] = int(request.form.get('progress', g.get('progress', 0)))
            g['category'] = request.form.get('category', g.get('category', 'Personal'))
            break
    save_data(data)
    return redirect(url_for('goals'))

@app.route('/delete-goal/<int:gid>', methods=['POST'])
def delete_goal(gid):
    data = load_data()
    data['goals'] = [g for g in data['goals'] if g['id'] != gid]
    save_data(data)
    return redirect(url_for('goals'))

@app.route('/add-milestone/<int:gid>', methods=['POST'])
def add_milestone(gid):
    data = load_data()
    title = (request.form.get('text') or request.form.get('title') or '').strip()
    if not title:
        return redirect(url_for('goals'))
    for g in data['goals']:
        if g['id'] == gid:
            existing = g.setdefault('milestones', [])
            # Safe unique ID: max existing + 1
            new_id = max((m['id'] for m in existing), default=0) + 1
            milestone = {
                'id': new_id,
                'title': title,
                'text': title,   # keep 'text' for backward compat
                'completed': False,
                'done': False,
                'created_at': datetime.now(_IST).isoformat(),
                'created': today_str()
            }
            existing.append(milestone)
            break
    save_data(data)
    return redirect(url_for('goals'))

@app.route('/delete-milestone/<int:gid>/<int:mid>', methods=['POST'])
def delete_milestone(gid, mid):
    data = load_data()
    for g in data['goals']:
        if g['id'] == gid:
            g['milestones'] = [m for m in g.get('milestones', []) if m['id'] != mid]
            break
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/toggle-milestone/<int:gid>/<int:mid>', methods=['POST'])
def toggle_milestone(gid, mid):
    data = load_data()
    for g in data['goals']:
        if g['id'] == gid:
            for m in g.get('milestones', []):
                if m['id'] == mid:
                    new_val = not m.get('completed', m.get('done', False))
                    m['completed'] = new_val
                    m['done'] = new_val
            break
    save_data(data)
    return jsonify({'status': 'ok'})

# ─── Sleep ───────────────────────────────────────────────────────────────────

@app.route('/sleep')
def sleep():
    data = load_data()
    logs = sorted(data['sleep_logs'], key=lambda x: x.get('date', ''), reverse=True)
    goal = data['settings'].get('daily_sleep_goal', 8)
    avg_sleep = sum(l.get('hours', 0) for l in logs[:7]) / max(len(logs[:7]), 1)
    return render_template('sleep.html', logs=logs, goal=goal,
                           avg_sleep=round(avg_sleep, 1), today=today_str())

@app.route('/add-sleep', methods=['POST'])
def add_sleep():
    data = load_data()
    sleep_time = request.form.get('sleep_time', '23:00')
    wake_time = request.form.get('wake_time', '07:00')
    # Calculate hours
    try:
        s = datetime.strptime(sleep_time, '%H:%M')
        w = datetime.strptime(wake_time, '%H:%M')
        if w < s:
            w = w.replace(day=w.day+1)
        hours = round((w - s).seconds / 3600, 1)
    except:
        hours = float(request.form.get('hours', 7))

    log = {
        'id': get_id(data['sleep_logs']),
        'date': request.form.get('date', today_str()),
        'sleep_time': sleep_time,
        'wake_time': wake_time,
        'hours': hours,
        'quality': request.form.get('quality', 'Good'),
        'notes': request.form.get('notes', '')
    }
    # Remove existing for same date
    data['sleep_logs'] = [l for l in data['sleep_logs'] if l.get('date') != log['date']]
    data['sleep_logs'].append(log)
    save_data(data)
    return redirect(url_for('sleep'))

@app.route('/delete-sleep/<int:lid>', methods=['POST'])
def delete_sleep(lid):
    data = load_data()
    data['sleep_logs'] = [l for l in data['sleep_logs'] if l.get('id') != lid]
    save_data(data)
    return redirect(url_for('sleep'))

# ─── Insights (Unified Analytics) ────────────────────────────────────────────

@app.route('/insights')
def insights():
    import calendar as cal_mod
    data = load_data()
    today_date = date.today()
    today = today_str()

    # ── Month params ──
    try:
        req_year  = int(request.args.get('year',  today_date.year))
        req_month = int(request.args.get('month', today_date.month))
    except:
        req_year  = today_date.year
        req_month = today_date.month
    month_name    = cal_mod.month_name[req_month]
    days_in_month = cal_mod.monthrange(req_year, req_month)[1]
    month_prefix  = f"{req_year}-{str(req_month).zfill(2)}"

    # ── 1. Monthly Overview ──────────────────────────────────
    month_exp = [e for e in data['expenses'] if e['date'].startswith(month_prefix)]
    total_spend = sum(e['amount'] for e in month_exp)
    cat_totals  = {}
    for e in month_exp:
        cat_totals[e['category']] = cat_totals.get(e['category'], 0) + e['amount']
    daily_spend = {}
    for e in month_exp:
        daily_spend[e['date']] = daily_spend.get(e['date'], 0) + e['amount']

    total_habit_completions = 0
    productive_days = 0
    daily_scores = []
    for day in range(1, days_in_month + 1):
        d = f"{month_prefix}-{str(day).zfill(2)}"
        logs = data['habit_logs'].get(d, [])
        total_habit_completions += len(logs)
        score = calc_productivity_score(data, d)
        if score is not None and score >= 70:
            productive_days += 1
        daily_scores.append({'date': d, 'score': score, 'day': day})
    real_scores = [s['score'] for s in daily_scores if s['score'] is not None]
    avg_score = round(sum(real_scores) / len(real_scores)) if real_scores else None

    chapters_done_month = 0
    for exam in data['exams']:
        for subj in exam.get('subjects', []):
            for ch in subj.get('chapters', []):
                if ch.get('completion_date', '').startswith(month_prefix):
                    chapters_done_month += 1
    for subj in data['subjects']:
        for ch in subj.get('chapters', []):
            if ch.get('completion_date', '').startswith(month_prefix):
                chapters_done_month += 1

    month_sleep = [l for l in data['sleep_logs'] if l.get('date', '').startswith(month_prefix)]
    avg_sleep = round(sum(l['hours'] for l in month_sleep) / len(month_sleep), 1) if month_sleep else 0

    scored = [s for s in daily_scores if s['score'] is not None and s['score'] > 0]
    best_day  = max(scored, key=lambda x: x['score']) if scored else None
    worst_day = min(scored, key=lambda x: x['score']) if scored else None

    weeks = []
    for week_num in range(1, 6):
        ws = (week_num - 1) * 7 + 1
        we = min(week_num * 7, days_in_month)
        if ws > days_in_month: break
        wsc = [s['score'] for s in daily_scores if ws <= s['day'] <= we and s['score'] is not None]
        weeks.append({'week': week_num,
                      'avg': round(sum(wsc)/len(wsc)) if wsc else None,
                      'days': f"{month_prefix}-{str(ws).zfill(2)} to {month_prefix}-{str(we).zfill(2)}"})

    month_options = []
    for i in range(12):
        d = today_date.replace(day=1) - timedelta(days=i*28)
        month_options.append({'year': d.year, 'month': d.month,
                               'label': f"{cal_mod.month_name[d.month]} {d.year}"})

    # ── 2. Daily Trends (7-day) ──────────────────────────────
    weekly_scores = []
    for i in range(6, -1, -1):
        d = (today_date - timedelta(days=i)).isoformat()
        weekly_scores.append({'date': d, 'score': calc_productivity_score(data, d)})

    habit_consistency = []
    for i in range(29, -1, -1):
        d = (today_date - timedelta(days=i)).isoformat()
        logs = data['habit_logs'].get(d, [])
        total = len(data['habits'])
        pct = round(len(logs) / total * 100) if total else 0
        habit_consistency.append({'date': d, 'pct': pct})

    sleep_trend = []
    for i in range(13, -1, -1):
        d = (today_date - timedelta(days=i)).isoformat()
        log = next((l for l in data['sleep_logs'] if l.get('date') == d), None)
        sleep_trend.append({'date': d, 'hours': log['hours'] if log else 0})

    # ── 3. Category Reports ──────────────────────────────────
    exams_progress = []
    for exam in data['exams']:
        total = sum(len(s.get('chapters', [])) for s in exam.get('subjects', []))
        done  = sum(1 for s in exam.get('subjects', []) for c in s.get('chapters', []) if c.get('status') == 'Completed')
        exams_progress.append({'name': exam['name'], 'progress': round(done/total*100) if total else 0,
                                'total': total, 'done': done})

    week_start_str = (today_date - timedelta(days=7)).isoformat()
    month_start_str = today_date.replace(day=1).isoformat()
    workout_logs_all = data.get('workout_logs', {})
    workouts_list = data.get('workouts', [])
    exercise_week_sessions  = sum(len(v) for d,v in workout_logs_all.items() if d >= week_start_str)
    exercise_week_mins      = sum(l.get('duration_minutes',0) for d,v in workout_logs_all.items() if d >= week_start_str for l in v)
    exercise_month_sessions = sum(len(v) for d,v in workout_logs_all.items() if d >= month_start_str)
    workout_stats = []
    for w in workouts_list:
        count = sum(1 for d,v in workout_logs_all.items() if any(l['workout_id']==w['id'] for l in v))
        workout_stats.append({'name': w['name'], 'count': count})
    workout_stats.sort(key=lambda x: x['count'], reverse=True)

    # ── 4. Performance Insights ──────────────────────────────
    habit_rates = []
    for h in data['habits']:
        count = sum(1 for i in range(30) if h['id'] in data['habit_logs'].get((today_date - timedelta(days=i)).isoformat(), []))
        habit_rates.append({'name': h['name'], 'rate': round(count/30*100)})
    habit_rates.sort(key=lambda x: x['rate'], reverse=True)

    # Study analytics — total hours per subject
    subject_analytics = []
    for exam in data['exams']:
        for subj in exam.get('subjects', []):
            total_ch = len(subj.get('chapters', []))
            done_ch  = sum(1 for c in subj.get('chapters', []) if c.get('status') == 'Completed')
            hours    = sum(s.get('duration', 0) for c in subj.get('chapters', []) for s in c.get('study_sessions', []))
            revisions = len(subj.get('revisions', []))
            subject_analytics.append({
                'name': subj['name'], 'exam': exam['name'],
                'total_ch': total_ch, 'done_ch': done_ch,
                'progress': round(done_ch/total_ch*100) if total_ch else 0,
                'hours': round(hours, 1), 'revisions': revisions,
                'avg_hrs_per_ch': round(hours/total_ch, 1) if total_ch else 0
            })
    for subj in data['subjects']:
        total_ch = len(subj.get('chapters', []))
        done_ch  = sum(1 for c in subj.get('chapters', []) if c.get('status') == 'Completed')
        hours    = sum(s.get('duration', 0) for c in subj.get('chapters', []) for s in c.get('study_sessions', []))
        revisions = len(subj.get('revisions', []))
        subject_analytics.append({
            'name': subj['name'], 'exam': 'Independent',
            'total_ch': total_ch, 'done_ch': done_ch,
            'progress': round(done_ch/total_ch*100) if total_ch else 0,
            'hours': round(hours, 1), 'revisions': revisions,
            'avg_hrs_per_ch': round(hours/total_ch, 1) if total_ch else 0
        })

    # Study streak
    study_streak = 0
    _chk = date.today()
    while True:
        _d = _chk.isoformat()
        has_study = any(
            c.get('start_date') == _d or c.get('completion_date') == _d
            for e in data['exams'] for s in e.get('subjects', []) for c in s.get('chapters', [])
        ) or any(
            c.get('start_date') == _d or c.get('completion_date') == _d
            for s in data['subjects'] for c in s.get('chapters', [])
        )
        if has_study:
            study_streak += 1
            _chk -= timedelta(days=1)
        else:
            break

    return render_template('insights.html',
        # Monthly overview
        month_name=month_name, req_year=req_year, req_month=req_month,
        days_in_month=days_in_month, month_prefix=month_prefix,
        total_spend=total_spend, cat_totals=cat_totals, daily_spend=daily_spend,
        total_habit_completions=total_habit_completions,
        productive_days=productive_days, avg_score=avg_score,
        daily_scores=daily_scores, chapters_done_month=chapters_done_month,
        avg_sleep=avg_sleep, best_day=best_day, worst_day=worst_day,
        weeks=weeks, month_options=month_options,
        currency=data['budget']['currency'], budget=data['budget']['monthly'],
        # Daily trends
        weekly_scores=weekly_scores, habit_consistency=habit_consistency,
        sleep_trend=sleep_trend,
        # Category reports
        exams_progress=exams_progress,
        exercise_week_sessions=exercise_week_sessions,
        exercise_week_mins=exercise_week_mins,
        exercise_month_sessions=exercise_month_sessions,
        workout_stats=workout_stats,
        month_total=total_spend,
        # Performance
        habit_rates=habit_rates,
        subject_analytics=subject_analytics,
        study_streak=study_streak
    )

# ─── Settings ────────────────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    data = load_data()
    if request.method == 'POST':
        data['settings']['name'] = request.form.get('name', 'Ayush')
        data['settings']['daily_sleep_goal'] = float(request.form.get('daily_sleep_goal', 8))
        budget_val = request.form.get('monthly_budget', '').strip()
        data['budget']['monthly'] = float(budget_val) if budget_val else 0
        data['budget']['currency'] = request.form.get('currency', '₹')
        save_data(data)
        return redirect(url_for('dashboard'))
    return render_template('settings.html', settings=data['settings'], budget=data['budget'])

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route('/api/calendar-data')
def calendar_data():
    data = load_data()
    today_date = date.today()
    result = {}
    for i in range(90):
        d = (today_date - timedelta(days=i)).isoformat()
        logs = data['habit_logs'].get(d, [])
        total_habits = len(data['habits'])
        pct = round(len(logs) / total_habits * 100) if total_habits else 0
        spend = sum(e['amount'] for e in data['expenses'] if e['date'] == d)
        prod = calc_productivity_score(data, d)  # may be None
        notes_count = len(data.get('notes', {}).get(d, []))
        # Only include day if it has some activity
        has_activity = pct > 0 or spend > 0 or prod is not None or notes_count > 0
        result[d] = {
            'habit_pct': pct, 'spend': round(spend, 2),
            'prod_score': prod,  # None = no data
            'notes': notes_count,
            'has_activity': has_activity
        }
    return jsonify(result)

# ─── API: Calendar extended ───────────────────────────────────────────────────

@app.route('/api/calendar-data-extended')
def calendar_data_extended():
    data = load_data()
    today_date = date.today()
    # Return 90 days for calendar
    result = {}
    for i in range(90):
        d = (today_date - timedelta(days=i)).isoformat()
        logs = data['habit_logs'].get(d, [])
        total_habits = len(data['habits'])
        pct = len(logs) / total_habits * 100 if total_habits else 0
        spend = sum(e['amount'] for e in data['expenses'] if e['date'] == d)
        prod = calc_productivity_score(data, d)
        notes_count = len(data.get('notes', {}).get(d, []))
        workout_count = len(data.get('workout_logs', {}).get(d, []))
        focus_mins    = sum(s.get('duration_minutes', 0)
                           for s in data.get('focus_timer_sessions', [])
                           if s.get('date') == d and s.get('completed'))
        result[d] = {
            'habit_pct':    round(pct),
            'spend':        round(spend, 2),
            'prod_score':   prod,
            'notes':        notes_count,
            'workout_count': workout_count,
            'focus_mins':   focus_mins,
            'has_activity': pct > 0 or spend > 0 or prod is not None
                            or notes_count > 0 or workout_count > 0 or focus_mins > 0
        }
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════
# EXERCISE SECTION
# ═══════════════════════════════════════════════════════════════

@app.route('/exercise')
def exercise():
    data = load_data()
    today = today_str()
    workouts = data.get('workouts', [])
    logs_today = data.get('workout_logs', {}).get(today, [])
    done_ids = [l['workout_id'] for l in logs_today]

    # Weekly stats
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    workout_logs_all = data.get('workout_logs', {})
    weekly_sessions = sum(
        len(logs) for d, logs in workout_logs_all.items() if d >= week_start
    )

    # Streaks
    streak = 0
    check = date.today()
    while True:
        d = check.isoformat()
        if data.get('workout_logs', {}).get(d):
            streak += 1
            check -= timedelta(days=1)
        else:
            break

    # Total minutes today
    total_mins_today = sum(l.get('duration_minutes', 0) for l in logs_today)

    # Personal bests per workout
    personal_bests = {}
    for w in workouts:
        best_reps = 0
        best_dist = 0.0
        best_dur  = 0
        all_reps_list = []
        for day_logs in workout_logs_all.values():
            for lg in day_logs:
                if lg['workout_id'] == w['id']:
                    try:
                        r = int(lg.get('reps') or 0)
                        if r > best_reps: best_reps = r
                        if r > 0: all_reps_list.append(r)
                    except: pass
                    try:
                        dst = float(str(lg.get('distance') or '0').split()[0])
                        if dst > best_dist: best_dist = dst
                    except: pass
                    try:
                        dur = int(lg.get('duration_minutes') or 0)
                        if dur > best_dur: best_dur = dur
                    except: pass
        # Suggest next target (10% above best)
        next_target = None
        if best_reps > 0:
            next_target = str(round(best_reps * 1.1))
        elif best_dist > 0:
            next_target = str(round(best_dist * 1.1, 1))
        elif best_dur > 0:
            next_target = str(round(best_dur * 1.1)) + 'm'
        personal_bests[w['id']] = {
            'reps': best_reps or None, 'distance': best_dist or None,
            'duration': best_dur or None, 'next_target': next_target,
            'all_reps': all_reps_list
        }
    return render_template('exercise.html',
        workouts=workouts, today=today, logs_today=logs_today,
        done_ids=done_ids, weekly_sessions=weekly_sessions,
        streak=streak, total_mins_today=total_mins_today,
        personal_bests=personal_bests
    )

@app.route('/add-workout', methods=['POST'])
def add_workout():
    data = load_data()
    workout = {
        'id': get_id(data.get('workouts', [])),
        'name': request.form['name'],
        'type': request.form.get('type', 'general'),
        'unit': request.form.get('unit', ''),
        'notes': request.form.get('notes', ''),
        'created': today_str()
    }
    data.setdefault('workouts', []).append(workout)
    save_data(data)
    return redirect(url_for('exercise'))

@app.route('/edit-workout/<int:wid>', methods=['POST'])
def edit_workout(wid):
    data = load_data()
    for w in data.get('workouts', []):
        if w['id'] == wid:
            w['name'] = request.form['name']
            w['type'] = request.form.get('type', w.get('type', 'general'))
            w['unit'] = request.form.get('unit', w.get('unit', ''))
            w['notes'] = request.form.get('notes', '')
            break
    save_data(data)
    return redirect(url_for('exercise'))

@app.route('/delete-workout/<int:wid>', methods=['POST'])
def delete_workout(wid):
    data = load_data()
    data['workouts'] = [w for w in data.get('workouts', []) if w['id'] != wid]
    save_data(data)
    return redirect(url_for('exercise'))

@app.route('/log-workout/<int:wid>', methods=['POST'])
def log_workout(wid):
    data = load_data()
    today = today_str()
    log_entry = {
        'workout_id': wid,
        'date': today,
        'sets': request.form.get('sets', ''),
        'reps': request.form.get('reps', ''),
        'weight': request.form.get('weight', ''),
        'distance': request.form.get('distance', ''),
        'duration_minutes': int(request.form.get('duration_minutes', 0) or 0),
        'notes': request.form.get('notes', ''),
        'logged_at': datetime.now(_IST).isoformat()
    }
    logs = data.setdefault('workout_logs', {}).setdefault(today, [])
    # Remove previous log for this workout today if exists
    logs[:] = [l for l in logs if l['workout_id'] != wid]
    logs.append(log_entry)
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/unlog-workout/<int:wid>', methods=['POST'])
def unlog_workout(wid):
    data = load_data()
    today = today_str()
    logs = data.get('workout_logs', {}).get(today, [])
    data['workout_logs'][today] = [l for l in logs if l['workout_id'] != wid]
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/exercise-history')
def exercise_history():
    data = load_data()
    workouts = {w['id']: w for w in data.get('workouts', [])}
    all_logs = data.get('workout_logs', {})
    # Last 30 days
    history = []
    for i in range(29, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        day_logs = all_logs.get(d, [])
        history.append({
            'date': d,
            'logs': day_logs,
            'total_mins': sum(l.get('duration_minutes', 0) for l in day_logs),
            'workout_count': len(day_logs)
        })
    return render_template('exercise_history.html', history=history, workouts=workouts)

@app.route('/api/exercise-data')
def api_exercise_data():
    data = load_data()
    today_date = date.today()
    result = {}
    for i in range(90):
        d = (today_date - timedelta(days=i)).isoformat()
        logs = data.get('workout_logs', {}).get(d, [])
        result[d] = {
            'workout_count': len(logs),
            'total_mins': sum(l.get('duration_minutes', 0) for l in logs)
        }
    return jsonify(result)



# ═══════════════════════════════════════════════════════════════
# AI ASSISTANT ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    """
    Structured Intent + Entity + Data Extraction chatbot.
    Stages: PARSE → CONFIRM → EXECUTE
    Pending confirmations stored in ai_pending (session via JSON body).
    """
    import re

    data      = load_data()
    body      = request.get_json() or {}
    user_msg  = (body.get('message') or '').strip()
    confirm   = body.get('confirm')       # True/False from user confirmation
    pending   = body.get('pending')       # dict sent back from previous turn

    if not user_msg and confirm is None:
        return jsonify({'reply': 'Please type or say something.', 'action': None})

    # ─────────────────────────────────────────────────────────
    # STAGE 3: User confirmed pending action → EXECUTE
    # ─────────────────────────────────────────────────────────
    if confirm is True and pending:
        result = _execute_pending(data, pending)
        save_data(data)
        return jsonify({'reply': result['reply'], 'action': result.get('action')})

    if confirm is False:
        return jsonify({'reply': '❌ Action cancelled. What else can I help with?', 'action': None})

    # ─────────────────────────────────────────────────────────
    # STAGE 1: Parse message → extract intents + entities
    # ─────────────────────────────────────────────────────────
    msg  = user_msg.lower().strip()
    parsed = _parse_message(msg, user_msg, data)

    if not parsed['intents']:
        # Fallback
        reply = (
            "I didn't understand that. Here are some examples:\n"
            "• \"Create GATE exam on 15 May\"\n"
            "• \"Add subject TOC\"\n"
            "• \"I spent 200 on food\"\n"
            "• \"I did 30 pushups\"\n"
            "• \"Add habit Morning Run\"\n"
            "• \"Today status\"\n"
            "• Hindi: \"aaj 30 pushups kiye\", \"200 kharch kiye food pe\""
        )
        return jsonify({'reply': reply, 'action': None})

    # ─────────────────────────────────────────────────────────
    # STAGE 2: Check for missing fields → ask clarification
    # ─────────────────────────────────────────────────────────
    missing = _check_missing(parsed['intents'])
    if missing['has_missing']:
        return jsonify({
            'reply': missing['question'],
            'action': {'type': 'clarification_needed'},
            'needs_clarification': True
        })

    # ─────────────────────────────────────────────────────────
    # Build confirmation message
    # ─────────────────────────────────────────────────────────
    # For status/log queries: execute directly without confirm
    direct_intents = {'status', 'list_exams', 'list_habits', 'list_goals'}
    if all(i['intent'] in direct_intents for i in parsed['intents']):
        result = _execute_pending(data, {'intents': parsed['intents']})
        save_data(data)
        return jsonify({'reply': result['reply'], 'action': result.get('action')})

    confirm_msg = _build_confirm_message(parsed['intents'])
    return jsonify({
        'reply':   confirm_msg,
        'action':  {'type': 'confirm_needed'},
        'needs_confirm': True,
        'pending': {'intents': parsed['intents']}
    })


# ─────────────────────────────────────────────────────────────
# PARSER: extract intents + entities from raw message
# ─────────────────────────────────────────────────────────────
def _parse_message(msg, raw, data):
    """
    Structured parser — strict entity/field separation.
    Handles both "create GATE exam" and "create exam GATE".
    Never merges name with date or other entity names.
    """
    import re
    from datetime import date as _dt, timedelta as _td

    intents = []

    # ── Date parser ───────────────────────────────────────────
    MONTHS = {
        'jan':1,'january':1,'feb':2,'february':2,'mar':3,'march':3,
        'apr':4,'april':4,'may':5,'jun':6,'june':6,'jul':7,'july':7,
        'aug':8,'august':8,'sep':9,'september':9,'oct':10,'october':10,
        'nov':11,'november':11,'dec':12,'december':12
    }
    MON_PAT = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|'
               r'jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|'
               r'nov(?:ember)?|dec(?:ember)?)')
    MON_CAP = (r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|'
               r'jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|'
               r'nov(?:ember)?|dec(?:ember)?)')

    def parse_date(text):
        if not text:
            return ''
        t = text.lower().strip()
        if 'tomorrow' in t:
            return (_dt.today() + _td(days=1)).isoformat()
        # "15 may" or "15th may"
        m = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+' + MON_CAP, t)
        if m:
            day = int(m.group(1))
            mon = MONTHS.get(m.group(2)[:3], 0)
            if mon:
                yr = _dt.today().year
                try:
                    d = _dt(yr, mon, day)
                    if d < _dt.today(): d = _dt(yr+1, mon, day)
                    return d.isoformat()
                except Exception: pass
        # "may 15"
        m2 = re.search(MON_CAP + r'\s+(\d{1,2})', t)
        if m2:
            mon = MONTHS.get(m2.group(1)[:3], 0)
            day = int(m2.group(2))
            if mon:
                yr = _dt.today().year
                try:
                    d = _dt(yr, mon, day)
                    if d < _dt.today(): d = _dt(yr+1, mon, day)
                    return d.isoformat()
                except Exception: pass
        # ISO
        m3 = re.search(r'(\d{4}-\d{2}-\d{2})', t)
        if m3: return m3.group(1)
        return ''

    # ── Number extractor ──────────────────────────────────────
    def first_num(text):
        nums = [n for n in re.findall(r'\d+(?:\.\d+)?', text)
                if not (len(n) == 4 and n.startswith('20'))]
        return float(nums[0]) if nums else None

    # ── "and" clause splitter ─────────────────────────────────
    # Split compound commands at " and " between different entity types
    # We detect entity types per sub-clause
    CREATE_KW = r'(?:create|add|new|make|banao?)'
    DATE_PAT  = (r'(?:\d{1,2}(?:st|nd|rd|th)?\s+' + MON_PAT +
                 r'|' + MON_PAT + r'\s+\d{1,2}|\d{4}-\d{2}-\d{2}|tomorrow)')

    # ─────────────────────────────────────────────────────────
    # STATUS / SUMMARY  (early return — no other intents)
    # ─────────────────────────────────────────────────────────
    STATUS_KW = ['status', 'how am i doing', 'today status', 'summary',
                 'my progress', 'show me my', 'daily summary', 'score today',
                 'what have i done']
    is_status = any(k in msg for k in STATUS_KW)
    # "aaj" alone = status if no exercise done-words follow
    if 'aaj' in msg and not any(k in msg for k in
            ['pushup','squat','run','walk','gym','yoga','exercise','kharcha','spent']):
        is_status = True
    if is_status and not any(k in msg for k in ['create','add','make','new','spent','paid']):
        intents.append({'intent': 'status', 'entity': None, 'fields': {}})
        return {'intents': intents, 'raw': raw}

    # ─────────────────────────────────────────────────────────
    # LIST
    # ─────────────────────────────────────────────────────────
    list_m = re.search(r'(?:list|show|display)\s+(?:all\s+)?(exams?|subjects?|habits?|goals?|tasks?)', msg)
    if list_m:
        etype = list_m.group(1).lower()
        intents.append({'intent': 'list_' + etype, 'entity': etype, 'fields': {}})
        return {'intents': intents, 'raw': raw}

    # ─────────────────────────────────────────────────────────
    # EXAM — handles both "create GATE exam" and "create exam GATE"
    # ─────────────────────────────────────────────────────────
    # Pattern A: create|add + NAME + exam + [on DATE]
    exam_a = re.search(
        CREATE_KW + r'\s+(?:an?\s+)?(?:new\s+)?'
        r'([a-z][a-z\s\d]{0,30}?)\s+exam'
        r'(?:\s+(?:on|date|scheduled?(?:\s+for)?)\s+(' + DATE_PAT + r'[^,;]*))?',
        msg)
    # Pattern B: create|add exam + NAME + [on DATE]
    exam_b = re.search(
        CREATE_KW + r'\s+(?:an?\s+)?(?:new\s+)?exam\s+'
        r'(?:named?|called?|of)?\s*'
        r'([a-z][a-z\s\d]{0,30}?)'
        r'(?:\s+(?:on|date|scheduled?(?:\s+for)?)\s+(' + DATE_PAT + r'[^,;]*))?$',
        msg)
    # Pick whichever matched
    exam_m = exam_a or exam_b
    if exam_m:
        ename = exam_m.group(1).strip()
        # Strip trailing "and", "on", prepositions that leaked in
        ename = re.sub(r'\s+(?:and|on|the|with|for|date)\s*$', '', ename, flags=re.I).strip().title()
        # Strip date-like words that leaked into name
        ename = re.sub(r'\s*\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s*$', '', ename, flags=re.I).strip()
        ename = re.sub(r'\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}\s*$', '', ename, flags=re.I).strip()
        edate_raw = exam_m.group(2) or ''
        edate = parse_date(edate_raw)
        # Reject single-word prepositions that slipped through
        BAD_NAMES = {'on','at','by','in','for','to','of','the','a','an'}
        if ename and len(ename) >= 2 and ename.lower() not in BAD_NAMES:
            intents.append({
                'intent': 'create_exam',
                'entity': 'exam',
                'fields': {'name': ename, 'date': edate, 'date_raw': edate_raw.strip()}
            })

    # ─────────────────────────────────────────────────────────
    # SUBJECT — stops before "and exam", "on", or date words
    # ─────────────────────────────────────────────────────────
    # Lookahead stops name at "and exam", "on \d", "under", "in exam" etc.
    subj_m = re.search(
        CREATE_KW + r'\s+(?:a\s+)?(?:new\s+)?subject\s+'
        r'(?:named?|called?|of)?\s*'
        r'([a-z][a-z\s\d]{0,30}?)'                     # subject name
        r'(?:\s+(?:in|for|under)\s+([a-z][\w\s]{0,30}?))?'   # optional exam ref
        r'(?=\s+and\s+(?:exam|chapter)|\s+on\s+\d|\s*$)',  # stop lookahead
        msg)
    if subj_m:
        sname = subj_m.group(1).strip()
        sname = re.sub(r'\s+(?:and|on|in|for|under|with)\s*$', '', sname, flags=re.I).strip().title()
        exam_ref = (subj_m.group(2) or '').strip()
        # Lookup exam id
        exam_id = None
        for ex in data.get('exams', []):
            if exam_ref and ex['name'].lower() in exam_ref.lower():
                exam_id = ex['id']
        if sname and len(sname) >= 1:
            intents.append({
                'intent': 'create_subject',
                'entity': 'subject',
                'fields': {'name': sname, 'exam_ref': exam_ref, 'exam_id': exam_id}
            })

    # ─────────────────────────────────────────────────────────
    # CHAPTER
    # ─────────────────────────────────────────────────────────
    chap_m = re.search(
        CREATE_KW + r'\s+(?:a\s+)?chapter\s+'
        r'(?:named?|called?)?\s*'
        r'([a-z][a-z\s\d]{0,30}?)'
        r'(?:\s+(?:in|for|under|to)\s+([\w\s]{0,30}))?$',
        msg)
    if chap_m:
        cname = chap_m.group(1).strip().title()
        sref  = (chap_m.group(2) or '').strip()
        intents.append({
            'intent': 'create_chapter',
            'entity': 'chapter',
            'fields': {'name': cname, 'subject_ref': sref}
        })

    # ─────────────────────────────────────────────────────────
    # MARK CHAPTER COMPLETE
    # ─────────────────────────────────────────────────────────
    if any(k in msg for k in ['chapter complete', 'chapter done', 'completed chapter',
                               'finished chapter', 'mark chapter']):
        cm = re.search(
            r'(?:completed?|finished?|done|mark)\s+(?:chapter\s+)?'
            r'([a-z][\w\s]{0,30}?)'
            r'(?:\s+(?:of|in|for)\s+([\w\s]{0,30}))?$', msg)
        if cm:
            intents.append({
                'intent': 'complete_chapter', 'entity': 'chapter',
                'fields': {'chapter_name': cm.group(1).strip().title(),
                           'subject_ref':  (cm.group(2) or '').strip()}
            })

    # ─────────────────────────────────────────────────────────
    # EXPENSE
    # ─────────────────────────────────────────────────────────
    EXPENSE_KW = ['spent', 'paid', 'bought', 'spend', 'purchase',
                  'kharcha', 'kharch', 'खर्च', 'liya', 'diya']
    amount_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:rs\.?|₹|rupees?|bucks?)?', msg)
    if any(k in msg for k in EXPENSE_KW) and amount_m:
        amount = float(amount_m.group(1))
        cat = 'Other'
        CAT_MAP = {
            'Food':          ['food','eat','lunch','dinner','breakfast','chai',
                              'tea','coffee','snack','restaurant','cafe','खाना'],
            'Travel':        ['travel','cab','bus','auto','metro','uber','ola',
                              'petrol','diesel','train','flight','ticket'],
            'Shopping':      ['shop','cloth','amazon','flipkart','buy','mall'],
            'Recharge':      ['recharge','mobile','phone','data','jio','airtel','sim'],
            'Education':     ['book','course','education','fee','tuition','coaching'],
            'Entertainment': ['movie','game','netflix','hotstar','ott','cinema'],
            'Health':        ['medicine','doctor','pharmacy','hospital','davai'],
            'Bills':         ['bill','electricity','rent','gas','cylinder'],
            'Investment':    ['invest','sip','mutual','stocks','crypto'],
        }
        for c, kws in CAT_MAP.items():
            if any(k in msg for k in kws):
                cat = c; break
        intents.append({
            'intent': 'log_expense', 'entity': 'expense',
            'fields': {'amount': amount, 'category': cat, 'description': raw[:60]}
        })

    # ─────────────────────────────────────────────────────────
    # EXERCISE — only when action words present; not inside create-habit
    # ─────────────────────────────────────────────────────────
    is_create_habit = bool(re.search(CREATE_KW + r'\s+(?:a\s+)?habit', msg))
    EX_KW   = ['pushup','pushups','squat','squats','run','running','walk','walking',
               'gym','workout','cycling','cycle','yoga','stretching','pullup',
               'pullups','plank','व्यायाम','कसरत']
    DONE_KW = ['did','done','kiya','kiye','completed','finished','aaj','today',
               'i do','karta','karte','kar','ki','kri']
    workout_found = next((w for w in data.get('workouts',[]) if w['name'].lower() in msg), None)

    if not is_create_habit and (any(k in msg for k in EX_KW) or workout_found) \
            and any(k in msg for k in DONE_KW):
        num = first_num(msg)
        wo_name = workout_found['name'] if workout_found else None
        if not wo_name:
            for kw in EX_KW:
                if kw in msg:
                    wo_name = (kw[:-1] if kw.endswith('s') and kw not in ('pushups','squats','pullups')
                               else kw).title()
                    break
        wo_type = 'reps'
        if any(k in msg for k in ['run','running','walk','walking','cycling','cycle']): wo_type='cardio'
        elif any(k in msg for k in ['yoga','stretch']): wo_type='flexibility'
        elif 'gym' in msg: wo_type='weights'
        intents.append({
            'intent': 'log_exercise', 'entity': 'exercise',
            'fields': {
                'workout_name': wo_name,
                'workout_id':   workout_found['id'] if workout_found else None,
                'type':         wo_type,
                'reps':         str(int(num)) if num and wo_type=='reps' else '',
                'distance':     str(num)       if num and wo_type=='cardio' else '',
                'duration':     str(int(num))  if num and wo_type in ('flexibility','duration') else '',
                'raw': raw
            }
        })

    # ─────────────────────────────────────────────────────────
    # HABIT CREATION
    # ─────────────────────────────────────────────────────────
    habit_m = re.search(
        CREATE_KW + r'\s+(?:a\s+)?habit\s+'
        r'(?:named?|called?|of)?\s*'
        r'([a-z][a-z\s\d]{1,40}?)(?:\s+(?:daily|every\s+day|weekly))?$',
        msg)
    if habit_m:
        intents.append({
            'intent': 'create_habit', 'entity': 'habit',
            'fields': {'name': habit_m.group(1).strip().title()}
        })

    # ─────────────────────────────────────────────────────────
    # GOAL
    # ─────────────────────────────────────────────────────────
    goal_m = re.search(
        CREATE_KW + r'\s+(?:a\s+)?(?:life\s+)?goal\s+'
        r'(?:named?|to|of)?\s*(.+?)(?:\s+by\s+(.+))?$',
        msg)
    if goal_m:
        intents.append({
            'intent': 'create_goal', 'entity': 'goal',
            'fields': {'title': goal_m.group(1).strip().title(),
                       'target_date': parse_date(goal_m.group(2) or '')}
        })

    # ─────────────────────────────────────────────────────────
    # TASK
    # ─────────────────────────────────────────────────────────
    task_m = re.search(
        CREATE_KW + r'\s+(?:a\s+)?task\s+(?:to\s+)?(.+?)'
        r'(?:\s+(?:on|by|due)\s+(.+))?$',
        msg)
    if task_m:
        tdate_raw = task_m.group(2) or ''
        tdate = parse_date(tdate_raw) if tdate_raw else today_str()
        intents.append({
            'intent': 'create_task', 'entity': 'task',
            'fields': {'title': task_m.group(1).strip().title(), 'date': tdate}
        })

    # ─────────────────────────────────────────────────────────
    # NOTE
    # ─────────────────────────────────────────────────────────
    note_m = re.search(
        r'(?:note|add\s+note|remember|save\s+this|write\s+down|नोट)\s+(.+)', msg)
    if note_m:
        intents.append({
            'intent': 'save_note', 'entity': 'note',
            'fields': {'text': note_m.group(1).strip()}
        })

    return {'intents': intents, 'raw': raw}


def _check_missing(intents):
    """Return clarification question if critical fields are missing."""
    questions = []
    for i in intents:
        intent = i['intent']
        fields = i['fields']
        if intent == 'create_exam':
            if not fields.get('name') or len(fields['name']) < 2:
                questions.append('What is the exam name?')
        if intent == 'create_subject':
            if not fields.get('name') or len(fields['name']) < 2:
                questions.append('What is the subject name?')
        if intent == 'log_expense':
            if not fields.get('amount') or fields['amount'] <= 0:
                questions.append('How much did you spend?')
        if intent == 'log_exercise':
            if not fields.get('workout_name'):
                questions.append('Which workout? (e.g. Pushups, Running, Gym)')
    if questions:
        return {'has_missing': True, 'question': '❓ ' + ' '.join(questions)}
    return {'has_missing': False}


def _build_confirm_message(intents):
    """Build a clear confirmation message showing what will be created."""
    lines = ['🔍 I detected the following actions. Confirm?', '']
    for i, intent_obj in enumerate(intents, 1):
        intent = intent_obj['intent']
        fields = intent_obj['fields']
        if intent == 'create_exam':
            date_str = fields.get('date') or '(not set)'
            lines.append(f'{i}. ➕ Create Exam: **{fields["name"]}**')
            lines.append(f'   📅 Date: {date_str}')
        elif intent == 'create_subject':
            lines.append(f'{i}. ➕ Create Subject: **{fields["name"]}**')
            if fields.get('exam_ref'):
                lines.append(f'   📋 Under exam: {fields["exam_ref"]}')
        elif intent == 'create_chapter':
            lines.append(f'{i}. ➕ Create Chapter: **{fields["name"]}**')
            if fields.get('subject_ref'):
                lines.append(f'   📚 Under subject: {fields["subject_ref"]}')
        elif intent == 'log_expense':
            lines.append(f'{i}. 💸 Log Expense: ₹{fields["amount"]:.0f} — {fields["category"]}')
        elif intent == 'log_exercise':
            wo = fields.get("workout_name","Workout")
            reps = fields.get("reps") or fields.get("distance") or fields.get("duration") or '?'
            lines.append(f'{i}. 💪 Log Exercise: {wo} — {reps}')
        elif intent == 'create_habit':
            lines.append(f'{i}. ✅ Create Habit: **{fields["name"]}**')
        elif intent == 'create_goal':
            lines.append(f'{i}. 🎯 Create Goal: **{fields["title"]}**')
        elif intent == 'create_task':
            lines.append(f'{i}. 📋 Create Task: **{fields["title"]}** on {fields["date"]}')
        elif intent == 'save_note':
            lines.append(f'{i}. 📝 Save Note: "{fields["text"][:50]}"')
        elif intent == 'complete_chapter':
            lines.append(f'{i}. ✓ Mark Complete: Chapter **{fields["chapter_name"]}**')
    lines.append('')
    lines.append('Reply **Yes** to confirm or **No** to cancel.')
    return chr(10).join(lines)


def _execute_pending(data, pending):
    """Execute all confirmed intents and return combined reply."""
    import re
    results = []
    actions = []

    for intent_obj in pending.get('intents', []):
        intent = intent_obj['intent']
        fields = intent_obj['fields']

        if intent == 'create_exam':
            ex = {
                'id': get_id(data['exams']), 'name': fields['name'],
                'date': fields.get('date',''), 'type': 'Other',
                'priority': 'Medium', 'status': 'Not Started',
                'notes': '', 'created': today_str(), 'subjects': []
            }
            data['exams'].append(ex)
            date_str = f" on {fields['date']}" if fields.get('date') else ''
            results.append(f'✅ Exam "{fields["name"]}"{date_str} created.')
            actions.append({'type': 'exam_created', 'name': fields['name']})

        elif intent == 'create_subject':
            all_ids = [s['id'] for s in data['subjects']] +                       [s['id'] for e in data['exams'] for s in e.get('subjects',[])]
            new_id  = (max(all_ids) + 1) if all_ids else 1
            subj = {
                'id': new_id, 'name': fields['name'], 'category': 'General',
                'priority': 'Medium', 'status': 'Not Started',
                'notes': '', 'weak_subject': False, 'start_date': today_str(),
                'resource_links': '', 'created': today_str(), 'chapters': [], 'revisions': [], 'manual_progress': 0
            }
            exam_id = fields.get('exam_id')
            if exam_id:
                for ex in data['exams']:
                    if ex['id'] == exam_id:
                        ex['subjects'].append(subj)
                        results.append(f'✅ Subject "{fields["name"]}" created under {ex["name"]}.')
                        break
            else:
                data['subjects'].append(subj)
                results.append(f'✅ Independent subject "{fields["name"]}" created.')
            actions.append({'type': 'subject_created', 'name': fields['name']})

        elif intent == 'create_chapter':
            # Find subject
            subj_ref = fields.get('subject_ref','').lower()
            target_subj = None
            for ex in data['exams']:
                for s in ex.get('subjects',[]):
                    if subj_ref in s['name'].lower() or s['name'].lower() in subj_ref:
                        target_subj = s
            if not target_subj:
                for s in data['subjects']:
                    if subj_ref in s['name'].lower() or s['name'].lower() in subj_ref:
                        target_subj = s
            if target_subj:
                chap_ids = [c['id'] for e in data['exams'] for s in e.get('subjects',[]) for c in s.get('chapters',[])] +                            [c['id'] for s in data['subjects'] for c in s.get('chapters',[])]
                new_cid = (max(chap_ids)+1) if chap_ids else 1
                chap = {
                    'id': new_cid, 'name': fields['name'], 'number': '',
                    'status': 'Not Started', 'revision_required': False,
                    'important': False, 'priority': 'Medium', 'notes': '',
                    'difficulty': 'Medium', 'estimated_hours': '', 'actual_hours': '',
                    'start_date': '', 'completion_date': '', 'created': today_str()
                }
                target_subj['chapters'].append(chap)
                results.append(f'✅ Chapter "{fields["name"]}" added to {target_subj["name"]}.')
                actions.append({'type': 'chapter_created'})
            else:
                results.append(f'⚠ Could not find subject "{subj_ref}". Open Study to add chapters manually.')

        elif intent == 'log_expense':
            exp = {
                'id': get_id(data['expenses']), 'amount': fields['amount'],
                'category': fields['category'], 'description': fields.get('description','AI log'),
                'date': today_str(), 'payment_method': 'Cash', 'tag': 'AI', 'created': today_str()
            }
            data['expenses'].append(exp)
            results.append(f'✅ ₹{fields["amount"]:.0f} logged under {fields["category"]}.')
            actions.append({'type': 'expense_added', 'amount': fields['amount'], 'category': fields['category']})

        elif intent == 'log_exercise':
            t = today_str()
            log_entry = {
                'workout_id': fields.get('workout_id', 0),
                'date': t, 'sets': '', 'reps': fields.get('reps',''),
                'weight': '', 'distance': fields.get('distance',''),
                'duration_minutes': int(fields.get('duration',0) or 0),
                'notes': fields.get('raw',''), 'logged_at': datetime.now(_IST).isoformat()
            }
            logs = data.setdefault('workout_logs',{}).setdefault(t,[])
            wid = fields.get('workout_id')
            if wid:
                logs[:] = [l for l in logs if l['workout_id'] != wid]
            logs.append(log_entry)
            reps = fields.get('reps') or fields.get('distance') or fields.get('duration')
            results.append(f'✅ {fields.get("workout_name","Workout")} logged' + (f' — {reps}' if reps else '') + '.')
            actions.append({'type': 'exercise_logged', 'workout': fields.get('workout_name')})

        elif intent == 'create_habit':
            h = {
                'id': get_id(data['habits']), 'name': fields['name'],
                'category': 'General', 'priority': 'Medium', 'frequency': 'Daily',
                'notes': '', 'color': '#4338ca', 'created': today_str()
            }
            data['habits'].append(h)
            results.append(f'✅ Habit "{fields["name"]}" created.')
            actions.append({'type': 'habit_created', 'name': fields['name']})

        elif intent == 'create_goal':
            g = {
                'id': get_id(data['goals']), 'title': fields['title'], 'description': '',
                'target_year': '', 'target_date': fields.get('target_date',''),
                'motivation': '', 'status': 'Pending', 'progress': 0,
                'category': 'Personal', 'created': today_str(),
                'milestones': [], 'linked_exams': []
            }
            data['goals'].append(g)
            results.append(f'✅ Goal "{fields["title"]}" created.')
            actions.append({'type': 'goal_created', 'name': fields['title']})

        elif intent == 'create_task':
            task = {
                'id': get_id(data['tasks']), 'title': fields['title'], 'description': '',
                'date': fields.get('date', today_str()), 'due_time': '',
                'priority': 'Medium', 'category': 'General', 'important': False,
                'completed': False, 'completed_at': '', 'created': today_str()
            }
            data['tasks'].append(task)
            results.append(f'✅ Task "{fields["title"]}" added to planner.')
            actions.append({'type': 'task_created', 'title': fields['title']})

        elif intent == 'save_note':
            td = today_str()
            note = {
                'id': sum(len(v) for v in data.get('notes',{}).values()) + 1,
                'text': fields['text'], 'category': 'AI', 'pinned': False,
                'created': datetime.now(_IST).isoformat()
            }
            data.setdefault('notes',{}).setdefault(td,[]).append(note)
            results.append(f'✅ Note saved: "{fields["text"][:50]}"')
            actions.append({'type': 'note_saved'})

        elif intent == 'complete_chapter':
            chap_ref = fields.get('chapter_name','').lower()
            found = False
            for ex in data['exams']:
                for s in ex.get('subjects',[]):
                    for c in s.get('chapters',[]):
                        if chap_ref in c['name'].lower() or c['name'].lower() in chap_ref:
                            c['status'] = 'Completed'
                            c['completion_date'] = today_str()
                            results.append(f'✅ Chapter "{c["name"]}" marked complete.')
                            found = True
                            break
            for s in data['subjects']:
                for c in s.get('chapters',[]):
                    if chap_ref in c['name'].lower():
                        c['status'] = 'Completed'
                        c['completion_date'] = today_str()
                        results.append(f'✅ Chapter "{c["name"]}" marked complete.')
                        found = True
            if not found:
                results.append(f'⚠ Chapter "{fields["chapter_name"]}" not found. Mark it manually in Study.')

        elif intent in ('status', 'list_exams', 'list_habits', 'list_goals'):
            reply = _build_status(data)
            results.append(reply)

    combined = chr(10).join(results) if results else '✅ Done!'
    combined_action = actions[0] if len(actions) == 1 else {'type': 'multi_action', 'count': len(actions)}
    return {'reply': combined, 'action': combined_action}


def _build_status(data):
    t = today_str()
    parts = [f'📊 Today — {t}:']
    habits_done  = len(data['habit_logs'].get(t, []))
    habits_total = len(data['habits'])
    if habits_total: parts.append(f'• Habits: {habits_done}/{habits_total} done')
    spend = sum(e['amount'] for e in data['expenses'] if e['date'] == t)
    if spend: parts.append(f'• Spent: ₹{spend:.0f}')
    wo = len(data.get('workout_logs',{}).get(t,[]))
    if wo: parts.append(f'• Workouts: {wo} done')
    focus = sum(s.get('duration_minutes',0) for s in data.get('focus_timer_sessions',[])
                if s.get('date') == t and s.get('completed'))
    if focus: parts.append(f'• Focus: {focus}m')
    score = calc_productivity_score(data, t)
    if score is not None: parts.append(f'• Score: {score}/100')
    # Upcoming exams
    exams_up = sorted([e for e in data['exams'] if e.get('date','') >= t], key=lambda x: x['date'])[:2]
    for ex in exams_up:
        try:
            from datetime import date as dt
            days = (dt.fromisoformat(ex['date']) - dt.today()).days
            parts.append(f'• Exam: {ex["name"]} in {days}d')
        except: pass
    if len(parts) == 1: parts.append('No activity logged yet today.')
    return chr(10).join(parts)



# ═══════════════════════════════════════════════════════════════
# REMEMBER SYSTEM
# ═══════════════════════════════════════════════════════════════

@app.route('/remember')
def remember():
    data = load_data()
    entries = data.get('remember', [])
    # Normalize legacy fields so the template never crashes on old data
    for e in entries:
        if not isinstance(e.get('tags'), list):
            e['tags'] = []
        if not e.get('type'):
            e['type'] = 'Other'
        if not e.get('status'):
            e['status'] = 'Active'
        if not e.get('description'):
            e['description'] = ''
        if not e.get('created_at'):
            e['created_at'] = ''
    entries = sorted(entries, key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('remember.html', entries=entries)

@app.route('/add-remember', methods=['POST'])
def add_remember():
    data = load_data()
    entry = {
        'id': get_id(data.get('remember', [])),
        'title': request.form.get('title','').strip(),
        'type': request.form.get('type', 'Notes'),
        'description': request.form.get('description',''),
        'tags': [t.strip() for t in request.form.get('tags','').split(',') if t.strip()],
        'created_at': datetime.now(_IST).isoformat(),
        'status': 'Active',
    }
    if not entry['title']:
        return redirect(url_for('remember'))
    data.setdefault('remember', []).append(entry)
    save_data(data)
    return redirect(url_for('remember'))

@app.route('/edit-remember/<int:rid>', methods=['POST'])
def edit_remember(rid):
    data = load_data()
    for e in data.get('remember', []):
        if e['id'] == rid:
            e['title']       = request.form.get('title', e['title']).strip()
            e['type']        = request.form.get('type', e.get('type', 'Notes'))
            e['description'] = request.form.get('description', e.get('description',''))
            e['tags']        = [t.strip() for t in request.form.get('tags','').split(',') if t.strip()]
            e['status']      = request.form.get('status', e.get('status','Active'))
            break
    save_data(data)
    return redirect(url_for('remember'))

@app.route('/delete-remember/<int:rid>', methods=['POST'])
def delete_remember(rid):
    data = load_data()
    data['remember'] = [e for e in data.get('remember', []) if e['id'] != rid]
    save_data(data)
    return redirect(url_for('remember'))

@app.route('/archive-remember/<int:rid>', methods=['POST'])
def archive_remember(rid):
    data = load_data()
    for e in data.get('remember', []):
        if e['id'] == rid:
            e['status'] = 'Archived' if e.get('status') == 'Active' else 'Active'
            break
    save_data(data)
    return jsonify({'status': 'ok'})

# ═══════════════════════════════════════════════════════════════
# GOAL LINKING SYSTEM
# ═══════════════════════════════════════════════════════════════

def _calc_goal_progress(data, goal):
    """Auto-calculate goal progress from linked exams."""
    linked = goal.get('linked_exams', [])
    if not linked:
        return goal.get('progress', 0)
    exam_map = {e['id']: e for e in data.get('exams', [])}
    progresses = []
    for eid in linked:
        ex = exam_map.get(eid)
        if ex:
            total = sum(len(s.get('chapters',[])) for s in ex.get('subjects',[]))
            done  = sum(1 for s in ex.get('subjects',[])
                        for c in s.get('chapters',[]) if c.get('status')=='Completed')
            progresses.append(round(done/total*100) if total else 0)
    return round(sum(progresses)/len(progresses)) if progresses else goal.get('progress', 0)

def _calc_goal_study_hours(data, goal):
    """Sum all study session hours from linked exams."""
    linked = goal.get('linked_exams', [])
    total_hrs = 0.0
    for ex in data.get('exams', []):
        if ex['id'] in linked:
            for subj in ex.get('subjects', []):
                for ch in subj.get('chapters', []):
                    for sess in ch.get('study_sessions', []):
                        total_hrs += sess.get('duration', 0)
    return round(total_hrs, 2)

@app.route('/link-exam-to-goal/<int:gid>', methods=['POST'])
def link_exam_to_goal(gid):
    data = load_data()
    eid = request.form.get('exam_id')
    if not eid:
        return jsonify({'status': 'error', 'msg': 'No exam_id'})
    eid = int(eid)
    exam_ids = [e['id'] for e in data.get('exams', [])]
    if eid not in exam_ids:
        return jsonify({'status': 'error', 'msg': 'Exam not found'})
    for g in data['goals']:
        if g['id'] == gid:
            linked = g.setdefault('linked_exams', [])
            if eid not in linked:
                linked.append(eid)
            break
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/unlink-exam-from-goal/<int:gid>/<int:eid>', methods=['POST'])
def unlink_exam_from_goal(gid, eid):
    data = load_data()
    for g in data['goals']:
        if g['id'] == gid:
            g['linked_exams'] = [e for e in g.get('linked_exams', []) if e != eid]
            break
    save_data(data)
    return jsonify({'status': 'ok'})

# ═══════════════════════════════════════════════════════════════
# UNIVERSAL START / STOP TRACKING
# ═══════════════════════════════════════════════════════════════

@app.route('/start-study-session', methods=['POST'])
def start_study_session():
    """Start a timed study session for a chapter (multiple allowed simultaneously)."""
    data        = load_data()
    chapter_id  = int(request.form.get('chapter_id', 0))
    subject_id  = int(request.form.get('subject_id', 0))
    custom_name = request.form.get('custom_name', '').strip()
    active_list = data.setdefault('active_sessions', {}).get('study') or []
    if isinstance(active_list, dict):          # migrate old single-session format
        active_list = [active_list] if active_list else []
    # For custom (free) sessions allow multiple with unique ts key
    if not (chapter_id == 0 and subject_id == 0):
        for s in active_list:
            if s.get('chapter_id') == chapter_id and s.get('subject_id') == subject_id:
                return jsonify({'status': 'already', 'start': s['start'],
                                'msg': 'Session already running for this chapter.'})
    new_session = {
        'chapter_id':   chapter_id,
        'subject_id':   subject_id,
        'custom_name':  custom_name,
        'start':        datetime.now(_IST).isoformat(),
        'date':         today_str()
    }
    active_list.append(new_session)
    data['active_sessions']['study'] = active_list
    save_data(data)
    return jsonify({'status': 'ok', 'start': new_session['start']})


@app.route('/stop-study-session', methods=['POST'])
def stop_study_session():
    """Stop a specific chapter's active session and save it."""
    data       = load_data()
    chapter_id = int(request.form.get('chapter_id', 0))
    subject_id = int(request.form.get('subject_id', 0))
    active_list = data.get('active_sessions', {}).get('study') or []
    if isinstance(active_list, dict):
        active_list = [active_list] if active_list else []
    # Find the matching running session
    target = next((s for s in active_list
                   if s.get('chapter_id') == chapter_id
                   and s.get('subject_id') == subject_id), None)
    if not target:
        return jsonify({'status': 'error', 'msg': 'No active session for this chapter.'})
    start_dt = datetime.fromisoformat(target['start'])
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=_IST)
    end_dt   = datetime.now(_IST)
    duration = round((end_dt - start_dt).total_seconds() / 3600, 4)
    session  = {
        'id':         int(datetime.now(_IST).timestamp()),
        'start':      target['start'],
        'end':        end_dt.isoformat(),
        'start_time': start_dt.strftime('%H:%M'),
        'end_time':   end_dt.strftime('%H:%M'),
        'duration':   duration,
        'date':       target.get('date', today_str()),
        'notes':      request.form.get('notes', '')
    }
    # Save into the chapter
    saved = False
    def _append(ch):
        nonlocal saved
        ch.setdefault('study_sessions', [])
        # Assign unique session id
        session['id'] = max((ss.get('id', 0) for ss in ch['study_sessions']), default=0) + 1
        ch['study_sessions'].append(session)
        ch['actual_hours'] = round(sum(ss.get('duration', 0) for ss in ch['study_sessions']), 2)
        saved = True
    for ex in data.get('exams', []):
        for subj in ex.get('subjects', []):
            if subj['id'] == subject_id:
                for ch in subj.get('chapters', []):
                    if ch['id'] == chapter_id:
                        _append(ch)
    for subj in data.get('subjects', []):
        if subj['id'] == subject_id:
            for ch in subj.get('chapters', []):
                if ch['id'] == chapter_id:
                    _append(ch)
    # Remove from active list
    data['active_sessions']['study'] = [
        s for s in active_list
        if not (s.get('chapter_id') == chapter_id and s.get('subject_id') == subject_id)
    ]
    save_data(data)
    mins = round(duration * 60, 1)
    return jsonify({'status': 'ok', 'duration_hours': duration,
                    'duration_mins': mins, 'saved': saved})


@app.route('/active-session-status')
def active_session_status():
    """Return all currently running study sessions with elapsed time."""
    data        = load_data()
    active_list = data.get('active_sessions', {}).get('study') or []
    if isinstance(active_list, dict):
        active_list = [active_list] if active_list else []

    # Build lookup maps: subject_id → name, (subject_id, chapter_id) → chapter_name
    subject_map = {}
    chapter_map = {}
    for subj in data.get('subjects', []):
        subject_map[subj['id']] = subj['name']
        for ch in subj.get('chapters', []):
            chapter_map[(subj['id'], ch['id'])] = ch['name']
    for exam in data.get('exams', []):
        for subj in exam.get('subjects', []):
            subject_map[subj['id']] = subj['name']
            for ch in subj.get('chapters', []):
                chapter_map[(subj['id'], ch['id'])] = ch['name']

    now = datetime.now(_IST)
    sessions = []
    for s in active_list:
        try:
            start_dt = datetime.fromisoformat(s['start'])
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=_IST)
            elapsed = (now - start_dt).total_seconds()
            sid = s.get('subject_id', 0)
            cid = s.get('chapter_id', 0)
            sessions.append({
                **s,
                'elapsed_seconds': round(elapsed),
                'subject_name': subject_map.get(sid, s.get('custom_name', 'Free Session')),
                'chapter_name': chapter_map.get((sid, cid), s.get('custom_name', 'Free Session')),
            })
        except Exception:
            pass
    return jsonify({'study': sessions})


# ── Reminders (stored client-side in localStorage via JS, routes only for
#    server-side scheduled push if needed in future) ──────────────────────────

@app.route('/api/reminders', methods=['GET'])
def get_reminders():
    """Return data needed to build smart reminders on the client."""
    data  = load_data()
    today = today_str()
    reminders = []

    # Habits — incomplete today
    done_today = set(data.get('habit_logs', {}).get(today, []))
    for h in data.get('habits', []):
        if h['id'] not in done_today:
            reminders.append({
                'id':       f"habit_{h['id']}",
                'type':     'habit',
                'title':    f"Habit: {h['name']}",
                'body':     "Not completed today",
                'priority': 'medium',
                'link':     '/habits'
            })

    # Tasks — due today or overdue, not completed
    for t in data.get('tasks', []):
        if not t.get('completed') and t.get('date', '') <= today and t.get('date'):
            overdue = t['date'] < today
            reminders.append({
                'id':       f"task_{t['id']}",
                'type':     'task',
                'title':    f"{'⚠ Overdue' if overdue else '📋 Due Today'}: {t['title']}",
                'body':     f"Priority: {t.get('priority','Medium')}",
                'priority': 'high' if overdue else 'medium',
                'link':     '/calendar'
            })

    # Exams — upcoming within 30 days
    from datetime import date as _date, timedelta
    today_d = _date.fromisoformat(today)
    for ex in data.get('exams', []):
        if ex.get('date'):
            try:
                exam_d = _date.fromisoformat(ex['date'])
                diff   = (exam_d - today_d).days
                if 0 <= diff <= 30:
                    reminders.append({
                        'id':       f"exam_{ex['id']}",
                        'type':     'exam',
                        'title':    f"📅 Exam: {ex['name']}",
                        'body':     'Today!' if diff == 0 else f"In {diff} day{'s' if diff != 1 else ''}",
                        'priority': 'high' if diff <= 3 else 'medium',
                        'link':     f"/exam/{ex['id']}"
                    })
            except ValueError:
                pass

    # Sleep — no log today
    sleep_today = any(s.get('date') == today for s in data.get('sleep_logs', []))
    if not sleep_today:
        reminders.append({
            'id':       'sleep_today',
            'type':     'sleep',
            'title':    '🌙 Sleep not logged today',
            'body':     'Track your sleep for better insights',
            'priority': 'low',
            'link':     '/sleep'
        })

    # Water — below goal
    goal  = data.get('settings', {}).get('daily_water_goal', 8)
    count = data.get('water_logs', {}).get(today, 0)
    if count < goal:
        reminders.append({
            'id':       'water_today',
            'type':     'water',
            'title':    f"💧 Water: {count}/{goal} glasses",
            'body':     f"{goal - count} more to reach your goal",
            'priority': 'low',
            'link':     '/dashboard'
        })

    # Study goals — chapters in progress with no session today
    for subj in data.get('subjects', []):
        for ch in subj.get('chapters', []):
            if ch.get('status') == 'In Progress':
                has_session_today = any(
                    ss.get('date') == today
                    for ss in ch.get('study_sessions', [])
                )
                if not has_session_today:
                    reminders.append({
                        'id':       f"study_{subj['id']}_{ch['id']}",
                        'type':     'study',
                        'title':    f"📚 Study: {ch['name']}",
                        'body':     f"In progress — no session logged today",
                        'priority': 'medium',
                        'link':     f"/subject/{subj['id']}"
                    })

    return jsonify({'reminders': reminders, 'count': len(reminders)})


@app.route('/api/chapters-list')
def api_chapters_list():
    """Return all chapters from all subjects and exams for the session panel."""
    data   = load_data()
    result = []
    # Standalone subjects
    for subj in data.get('subjects', []):
        for ch in subj.get('chapters', []):
            sessions_today = [
                ss for ss in ch.get('study_sessions', [])
                if ss.get('date') == today_str()
            ]
            total_today = round(sum(ss.get('duration', 0) for ss in sessions_today) * 60)
            result.append({
                'subject_id':    subj['id'],
                'subject_name':  subj['name'],
                'chapter_id':    ch['id'],
                'chapter_name':  ch['name'],
                'status':        ch.get('status', 'Not Started'),
                'priority':      ch.get('priority', 'Medium'),
                'actual_hours':  ch.get('actual_hours', 0),
                'total_sessions':len(ch.get('study_sessions', [])),
                'today_mins':    total_today,
                'source':        'subject',
                'exam_name':     None,
            })
    # Exam subjects
    for ex in data.get('exams', []):
        for subj in ex.get('subjects', []):
            for ch in subj.get('chapters', []):
                sessions_today = [
                    ss for ss in ch.get('study_sessions', [])
                    if ss.get('date') == today_str()
                ]
                total_today = round(sum(ss.get('duration', 0) for ss in sessions_today) * 60)
                result.append({
                    'subject_id':    subj['id'],
                    'subject_name':  subj['name'],
                    'chapter_id':    ch['id'],
                    'chapter_name':  ch['name'],
                    'status':        ch.get('status', 'Not Started'),
                    'priority':      ch.get('priority', 'Medium'),
                    'actual_hours':  ch.get('actual_hours', 0),
                    'total_sessions':len(ch.get('study_sessions', [])),
                    'today_mins':    total_today,
                    'source':        'exam',
                    'exam_name':     ex['name'],
                })
    return jsonify({'chapters': result})

@app.route('/start-sleep', methods=['POST'])
def start_sleep():
    data = load_data()
    data.setdefault('active_sessions', {})['sleep'] = {
        'start': datetime.now(_IST).isoformat(),
        'date': today_str()
    }
    save_data(data)
    return jsonify({'status': 'ok'})

@app.route('/stop-sleep', methods=['POST'])
def stop_sleep_session():
    data = load_data()
    active = data.get('active_sessions', {}).get('sleep')
    if not active:
        return jsonify({'status': 'error', 'msg': 'No active sleep session.'})
    start_dt = datetime.fromisoformat(active['start'])
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=_IST)
    end_dt   = datetime.now(_IST)
    hours    = round((end_dt - start_dt).total_seconds() / 3600, 2)
    start_t  = start_dt.strftime('%H:%M')
    end_t    = end_dt.strftime('%H:%M')
    log = {
        'id': get_id(data.get('sleep_logs', [])),
        'date': active.get('date', today_str()),
        'sleep_time': start_t, 'wake_time': end_t,
        'hours': hours, 'quality': 'Good', 'notes': 'Auto-tracked'
    }
    data.setdefault('sleep_logs', []).append(log)
    data['active_sessions']['sleep'] = None
    save_data(data)
    return jsonify({'status': 'ok', 'hours': hours})

# ═══════════════════════════════════════════════════════════════
# GOALS PAGE — updated with auto-progress and linking
# ═══════════════════════════════════════════════════════════════

@app.route('/goals')
def goals():
    data = load_data()
    gs = data['goals']
    exam_map = {e['id']: e['name'] for e in data.get('exams', [])}
    all_exams = data.get('exams', [])
    # Auto-calc progress + study hours per goal
    for g in gs:
        g.setdefault('linked_exams', [])
        g.setdefault('milestones', [])
        # Sync milestone fields
        for m in g['milestones']:
            if 'completed' not in m: m['completed'] = m.get('done', False)
            if 'title' not in m:     m['title']     = m.get('text', '')
        g['auto_progress']  = _calc_goal_progress(data, g)
        g['study_hours']    = _calc_goal_study_hours(data, g)
        g['linked_exam_names'] = [exam_map.get(eid,'?') for eid in g['linked_exams']]
        total_ms = len(g['milestones'])
        done_ms  = sum(1 for m in g['milestones'] if m.get('completed') or m.get('done'))
        g['milestone_pct'] = round(done_ms/total_ms*100) if total_ms else 0
    completed  = [g for g in gs if g['status'] == 'Completed']
    in_progress= [g for g in gs if g['status'] == 'In Progress']
    pending    = [g for g in gs if g['status'] == 'Pending']
    return render_template('goals.html', goals=gs, completed=completed,
                           in_progress=in_progress, pending=pending,
                           all_exams=all_exams)

# ═══════════════════════════════════════════════════════════════
# STUDY SESSION TIMER — Dedicated full-page module
# ═══════════════════════════════════════════════════════════════

@app.route('/study-timer')
def study_timer():
    """Dedicated Study Session Timer page."""
    data = load_data()
    return render_template('study_timer.html',
                           settings=data.get('settings', {}),
                           currency=data['budget']['currency'])


@app.route('/api/study-sessions')
def api_study_sessions():
    """
    Return ALL study sessions across every subject/chapter as a flat list.
    Each item includes: sess_id, subject_id, subject_name, chapter_id,
    chapter_name, date, start_time, end_time, duration, notes, status.
    """
    data = load_data()
    sessions = []

    def _collect(subj, exam_name=None):
        for ch in subj.get('chapters', []):
            for ss in ch.get('study_sessions', []):
                # Duration in hours → keep as float; UI converts to minutes
                duration = ss.get('duration', 0)
                sessions.append({
                    'sess_id':      ss.get('id', 0),
                    'subject_id':   subj['id'],
                    'subject_name': subj['name'],
                    'chapter_id':   ch['id'],
                    'chapter_name': ch['name'],
                    'exam_name':    exam_name,
                    'date':         ss.get('date', ''),
                    'start_time':   ss.get('start_time') or (ss['start'][11:16] if ss.get('start') and len(ss['start']) > 10 else ''),
                    'end_time':     ss.get('end_time') or (ss['end'][11:16] if ss.get('end') and len(ss['end']) > 10 else ''),
                    'duration':     round(duration, 4),
                    'notes':        ss.get('notes', ''),
                    'status':       'Completed',
                })

    for subj in data.get('subjects', []):
        _collect(subj, None)
    for exam in data.get('exams', []):
        for subj in exam.get('subjects', []):
            _collect(subj, exam['name'])

    # Sort newest-first
    sessions.sort(key=lambda x: (x['date'], x['start_time']), reverse=True)
    return jsonify({'sessions': sessions, 'total': len(sessions)})


@app.route('/api/edit-study-session', methods=['POST'])
def api_edit_study_session():
    """Edit start/end time and notes of an existing session."""
    data       = load_data()
    sess_id    = int(request.form.get('sess_id', 0))
    subject_id = int(request.form.get('subject_id', 0))
    chapter_id = int(request.form.get('chapter_id', 0))
    start_t    = request.form.get('start_time', '')
    end_t      = request.form.get('end_time', '')
    notes      = request.form.get('notes', '')

    # Recalculate duration from new times
    duration = 0.0
    if start_t and end_t:
        try:
            s_dt = datetime.strptime(start_t, '%H:%M')
            e_dt = datetime.strptime(end_t,   '%H:%M')
            if e_dt <= s_dt:
                e_dt = e_dt.replace(day=e_dt.day + 1)
            duration = round((e_dt - s_dt).total_seconds() / 3600, 4)
        except Exception:
            pass

    def _edit(chapters):
        for ch in chapters:
            if ch['id'] == chapter_id:
                for ss in ch.get('study_sessions', []):
                    if ss.get('id') == sess_id:
                        ss['start_time'] = start_t
                        ss['end_time']   = end_t
                        ss['notes']      = notes
                        if duration > 0:
                            ss['duration'] = duration
                        # Re-sync actual_hours
                        ch['actual_hours'] = round(
                            sum(s.get('duration', 0) for s in ch['study_sessions']), 2)
                        return True
        return False

    found = False
    for subj in data.get('subjects', []):
        if subj['id'] == subject_id and _edit(subj.get('chapters', [])):
            found = True; break
    if not found:
        for exam in data.get('exams', []):
            for subj in exam.get('subjects', []):
                if subj['id'] == subject_id and _edit(subj.get('chapters', [])):
                    found = True; break
            if found:
                break

    if found:
        save_data(data)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'msg': 'Session not found'})


@app.route('/api/delete-study-session', methods=['POST'])
def api_delete_study_session():
    """Delete a specific study session by sess_id."""
    data       = load_data()
    sess_id    = int(request.form.get('sess_id', 0))
    subject_id = int(request.form.get('subject_id', 0))
    chapter_id = int(request.form.get('chapter_id', 0))

    def _delete(chapters):
        for ch in chapters:
            if ch['id'] == chapter_id:
                before = len(ch.get('study_sessions', []))
                ch['study_sessions'] = [
                    ss for ss in ch.get('study_sessions', [])
                    if ss.get('id') != sess_id
                ]
                if len(ch['study_sessions']) < before:
                    ch['actual_hours'] = round(
                        sum(s.get('duration', 0) for s in ch['study_sessions']), 2)
                    return True
        return False

    found = False
    for subj in data.get('subjects', []):
        if subj['id'] == subject_id and _delete(subj.get('chapters', [])):
            found = True; break
    if not found:
        for exam in data.get('exams', []):
            for subj in exam.get('subjects', []):
                if subj['id'] == subject_id and _delete(subj.get('chapters', [])):
                    found = True; break
            if found:
                break

    if found:
        save_data(data)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'msg': 'Session not found'})


if __name__ == '__main__':
    app.run(debug=True, port=5000)