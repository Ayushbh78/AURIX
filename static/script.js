/* ══════════════════════════════════════════════════
   AURIX — Main JS  (Dark Theme Only)
   ══════════════════════════════════════════════════ */

// Always dark theme
document.documentElement.setAttribute('data-theme', 'dark');

// ─── SIDEBAR ────────────────────────────────────────
function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('overlay').classList.add('active');
  document.body.style.overflow = 'hidden';
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('overlay').classList.remove('active');
  document.body.style.overflow = '';
}
document.querySelectorAll('.nav-item').forEach(i => i.addEventListener('click', () => {
  if (window.innerWidth < 900) closeSidebar();
}));

// ─── MODAL SYSTEM ────────────────────────────────────
function openModal(id) {
  const src = document.getElementById(id);
  if (!src) return;
  const ov  = document.getElementById('modal-overlay');
  const box = document.getElementById('active-modal');
  box.innerHTML = src.innerHTML;
  ov.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  const today = new Date().toISOString().split('T')[0];
  box.querySelectorAll('input[type="date"]').forEach(el => { if (!el.value) el.value = today; });
}
function closeModal(e) {
  if (e && e.target !== document.getElementById('modal-overlay')) return;
  closeActiveModal();
}
function closeActiveModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('active-modal').innerHTML = '';
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeActiveModal(); });

// ─── DATE/TIME ───────────────────────────────────────
function updateDateTime() {
  const now = new Date();
  const s = now.toLocaleDateString('en-IN', {weekday:'short',month:'short',day:'numeric',year:'numeric'})
          + ' · ' + now.toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit'});
  const el = document.getElementById('topbar-date');
  if (el) el.textContent = s;
}
updateDateTime();
setInterval(updateDateTime, 30000);

// ─── PROGRESS BAR ANIMATION ─────────────────────────
function animateBars() {
  const sel = '.progress-bar,.big-progress-fill,.study-progress-fill,.goal-progress-fill,.habit-progress-fill,.subject-mini-fill,.cat-bar,.week-bar';
  document.querySelectorAll(sel).forEach(b => {
    const w = b.style.width;
    if (!w || w === '0%' || w === '0') return;
    b.style.transition = 'none'; b.style.width = '0';
    setTimeout(() => { b.style.transition = ''; b.style.width = w; }, 80);
  });
}

// ─── GLOBAL SEARCH ───────────────────────────────────
let searchTimeout = null;
function globalSearch(q) {
  const res = document.getElementById('search-results');
  if (!res) return;
  clearTimeout(searchTimeout);
  if (!q.trim()) { res.style.display = 'none'; return; }
  searchTimeout = setTimeout(() => {
    fetch('/api/search?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(data => {
        if (!data.length) { res.innerHTML = '<div class="sr-empty">No results found</div>'; }
        else {
          const icons = {habit:'✅',expense:'💸',exam:'📋',subject:'📚',goal:'🎯',note:'📝'};
          res.innerHTML = data.map(d => `
            <a href="${d.url}" class="sr-item">
              <span class="sr-icon">${icons[d.type]||'📌'}</span>
              <div class="sr-body"><div class="sr-title">${d.title}</div><div class="sr-sub">${d.type} · ${d.sub||''}</div></div>
            </a>`).join('');
        }
        res.style.display = 'block';
      });
  }, 280);
}
document.addEventListener('click', e => {
  const wrap = document.querySelector('.global-search-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const r = document.getElementById('search-results');
    if (r) r.style.display = 'none';
  }
});

// ─── HABIT TOGGLE ────────────────────────────────────
function toggleHabit(id) {
  fetch('/toggle-habit/' + id, {method:'POST'})
    .then(r => r.json())
    .then(d => {
      const card  = document.getElementById('hcard-' + id);
      const pills = document.querySelectorAll('[data-hid="' + id + '"]');
      if (card) card.classList.toggle('habit-card-done', d.completed);
      pills.forEach(p => {
        if (p.classList.contains('habit-quick-pill')) {
          p.classList.toggle('habit-pill-done', d.completed);
          const chk = p.querySelector('.pill-check');
          if (chk) chk.textContent = d.completed ? '✓' : '○';
        } else {
          p.classList.toggle('habit-toggle-done', d.completed);
          p.textContent = d.completed ? '✓ Done' : 'Mark Done';
        }
      });
      const total = parseInt(document.getElementById('habit-total')?.textContent || '0');
      if (total > 0) {
        const pct = Math.round(d.count / total * 100);
        const fill = document.getElementById('main-progress-fill');
        if (fill) fill.style.width = pct + '%';
        const lbl = document.getElementById('habit-pct-label');
        if (lbl) lbl.textContent = pct + '%';
      }
    });
}

// ─── TASK TOGGLE ─────────────────────────────────────
function toggleTask(id) {
  fetch('/toggle-task/' + id, {method:'POST'})
    .then(() => { location.reload(); });
}

// ─── CHAPTER QUICK STATUS ────────────────────────────
function quickUpdateChapter(sid, cid, status) {
  const fd = new FormData(); fd.append('status', status);
  fetch(`/toggle-chapter/${sid}/${cid}`, {method:'POST', body:fd})
    .then(() => { location.reload(); });
}

// ─── EXPENSE FILTER ──────────────────────────────────
function filterExpenses(q) {
  document.querySelectorAll('.expense-row').forEach(row => {
    const match = (row.dataset.desc||'').toLowerCase().includes(q.toLowerCase())
               || (row.dataset.cat||'').toLowerCase().includes(q.toLowerCase());
    row.style.display = match ? '' : 'none';
  });
}

// ─── MOOD LOG ────────────────────────────────────────
function logMood(mood, date) {
  fetch('/log-mood', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:'mood='+encodeURIComponent(mood)+'&date='+date})
    .then(() => { closeActiveModal(); showToast('Mood: ' + mood, 'success'); });
}

// ─── TOAST ───────────────────────────────────────────
function showToast(msg, type='info') {
  let t = document.getElementById('app-toast');
  if (!t) {
    t = document.createElement('div'); t.id = 'app-toast';
    document.body.appendChild(t);
  }
  t.className = 'app-toast toast-' + type;
  t.textContent = msg;
  t.style.transform = 'translateY(0)';
  clearTimeout(t._t);
  t._t = setTimeout(() => { t.style.transform = 'translateY(100px)'; }, 3000);
}

// ─── BAR CHART TOOLTIPS ──────────────────────────────
function initBarTooltips() {
  document.querySelectorAll('.bar-chart-bar[data-tip]').forEach(b => {
    b.addEventListener('mouseenter', e => {
      let tip = document.getElementById('bar-tip');
      if (!tip) {
        tip = document.createElement('div'); tip.id = 'bar-tip';
        tip.style.cssText = 'position:fixed;background:var(--text);color:var(--bg);font-size:11px;padding:4px 10px;border-radius:6px;pointer-events:none;z-index:9999;font-family:var(--mono);white-space:nowrap';
        document.body.appendChild(tip);
      }
      tip.textContent = b.dataset.tip; tip.style.display = 'block';
    });
    b.addEventListener('mousemove', e => {
      const tip = document.getElementById('bar-tip');
      if (tip) { tip.style.left=(e.clientX+12)+'px'; tip.style.top=(e.clientY-30)+'px'; }
    });
    b.addEventListener('mouseleave', () => {
      const tip = document.getElementById('bar-tip'); if (tip) tip.style.display = 'none';
    });
  });
}

// ─── KEYBOARD SHORTCUTS ──────────────────────────────
document.addEventListener('keydown', e => {
  if (e.altKey && !e.ctrlKey) {
    const map = {d:'/dashboard',h:'/habits',s:'/spending',
                 e:'/study',c:'/calendar',n:'/notes',g:'/goals',z:'/sleep',
                 i:'/insights',t:'/thoughts',r:'/remember'};
    if (map[e.key]) { e.preventDefault(); window.location.href = map[e.key]; }
  }
});

// ─── INIT ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  animateBars();
  initBarTooltips();
  const today = new Date().toISOString().split('T')[0];
  document.querySelectorAll('input[type="date"]').forEach(el => { if (!el.value) el.value = today; });
  document.body.style.overflow = '';
});

/* ══════════════════════════════════════════════════
   MILESTONE FUNCTIONS
   ══════════════════════════════════════════════════ */
function toggleMilestone(gid, mid, btn) {
  fetch(`/toggle-milestone/${gid}/${mid}`, {method: 'POST'})
    .then(r => r.json())
    .then(() => {
      const item = btn.closest('.milestone-item');
      const span = item.querySelector('span');
      const isDone = btn.textContent.trim() === '✓';
      if (isDone) {
        btn.textContent = '○';
        item.classList.remove('milestone-done');
        span.classList.remove('line-through','text-muted');
      } else {
        btn.textContent = '✓';
        item.classList.add('milestone-done');
        span.classList.add('line-through','text-muted');
      }
    })
    .catch(() => showToast('Error toggling milestone', 'error'));
}

function deleteMilestone(gid, mid, btn) {
  if (!confirm('Delete this milestone?')) return;
  fetch(`/delete-milestone/${gid}/${mid}`, {method: 'POST'})
    .then(r => r.json())
    .then(() => {
      const item = btn.closest('.milestone-item');
      item.remove();
      showToast('Milestone deleted', 'success');
    })
    .catch(() => showToast('Error deleting milestone', 'error'));
}

/* ══════════════════════════════════════════════════
   GOAL EXAM LINKING
   ══════════════════════════════════════════════════ */
let _unlinkTarget = {};

function linkExam(gid) {
  const sel = document.getElementById('link-select-' + gid);
  if (!sel || !sel.value) { showToast('Select an exam first', 'warn'); return; }
  const btn = document.getElementById('link-btn-' + gid);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="link-btn-spinner"></span><span class="link-btn-text">Linking…</span>';
    btn.classList.add('link-btn-loading');
  }
  const fd = new FormData();
  fd.append('exam_id', sel.value);
  fetch(`/link-exam-to-goal/${gid}`, {method:'POST', body:fd})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        if (btn) {
          btn.classList.remove('link-btn-loading');
          btn.classList.add('link-btn-success');
          btn.innerHTML = '<span>✔ Linked</span>';
        }
        setTimeout(() => { location.reload(); }, 600);
      } else {
        if (btn) { btn.disabled = false; btn.innerHTML = '<span class="link-btn-icon">🔗</span><span class="link-btn-text">Link Exam</span>'; btn.classList.remove('link-btn-loading'); }
        showToast(d.msg || 'Error linking', 'error');
      }
    });
}

function confirmUnlink(gid, eid, ename) {
  _unlinkTarget = {gid, eid};
  const msg = document.getElementById('unlink-msg-' + gid);
  if (msg) msg.textContent = `Remove link to "${ename}" from this goal?`;
  openModal('modal-unlink-' + gid);
}

function doUnlink(gid) {
  const {eid} = _unlinkTarget;
  const badge = document.getElementById(`badge-${gid}-${eid}`);
  if (badge) { badge.style.opacity = '0'; badge.style.transform = 'scale(0.85)'; badge.style.transition = 'all 0.3s'; }
  closeActiveModal();
  setTimeout(() => {
    fetch(`/unlink-exam-from-goal/${gid}/${eid}`, {method:'POST'})
      .then(r => r.json())
      .then(() => { showToast('Exam unlinked', 'success'); location.reload(); });
  }, 300);
}

function unlinkExam(gid, eid) { _unlinkTarget = {gid, eid}; doUnlink(gid); }

/* ══════════════════════════════════════════════════
   UNIVERSAL START/STOP STUDY SESSION
   ══════════════════════════════════════════════════ */
let studyTimerInterval = null;

function startStudySession(chapterId, subjectId, btnEl) {
  const fd = new FormData();
  fd.append('chapter_id', chapterId);
  fd.append('subject_id', subjectId);
  fetch('/start-study-session', {method: 'POST', body: fd})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        showToast('Study session started ▶', 'success');
        if (btnEl) {
          btnEl.textContent = '⏹ Stop';
          btnEl.className = 'btn-stop-study';
          btnEl.onclick = () => stopStudySession(chapterId, subjectId, btnEl);
        }
        const timerEl = document.getElementById(`study-timer-${chapterId}`);
        if (timerEl) {
          let secs = 0;
          studyTimerInterval = setInterval(() => {
            secs++;
            const m = Math.floor(secs / 60), s = secs % 60;
            timerEl.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
          }, 1000);
        }
      } else {
        showToast(d.msg || 'Could not start session', 'warn');
      }
    });
}

function stopStudySession(chapterId, subjectId, btnEl) {
  fetch('/stop-study-session', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        clearInterval(studyTimerInterval);
        const mins = d.duration_mins || 0;
        showToast(`Session saved: ${mins}m`, 'success');
        if (btnEl) {
          btnEl.textContent = '▶ Start';
          btnEl.className = 'btn-start-study';
          btnEl.onclick = () => startStudySession(chapterId, subjectId, btnEl);
        }
        const timerEl = document.getElementById(`study-timer-${chapterId}`);
        if (timerEl) timerEl.textContent = '00:00';
        setTimeout(() => { location.reload(); }, 800);
      } else {
        showToast(d.msg || 'No active session', 'warn');
      }
    });
}

function checkActiveStudySession() {
  fetch('/active-session-status')
    .then(r => r.json())
    .then(d => {
      if (d.study) {
        const cid = d.study.chapter_id;
        const sid = d.study.subject_id;
        const elapsed = d.study.elapsed_seconds || 0;
        const timerEl = document.getElementById(`study-timer-${cid}`);
        if (timerEl) {
          let secs = elapsed;
          studyTimerInterval = setInterval(() => {
            secs++;
            const m = Math.floor(secs / 60), s = secs % 60;
            timerEl.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
          }, 1000);
        }
        const btn = document.getElementById(`study-btn-${cid}`);
        if (btn) {
          btn.textContent = '⏹ Stop';
          btn.className = 'btn-stop-study';
          btn.onclick = () => stopStudySession(cid, sid, btn);
        }
      }
    }).catch(() => {});
}

/* ══════════════════════════════════════════════════
   SLEEP START/STOP
   ══════════════════════════════════════════════════ */
function startSleepTracking() {
  fetch('/start-sleep', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') showToast('Sleep tracking started 🌙', 'success');
    });
}

function stopSleepTracking() {
  fetch('/stop-sleep', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        showToast(`Sleep logged: ${d.hours}h`, 'success');
        setTimeout(() => { location.reload(); }, 800);
      } else {
        showToast(d.msg || 'No active sleep session', 'warn');
      }
    });
}

document.addEventListener('DOMContentLoaded', () => {
  checkActiveStudySession();
});

// ─── Touch/scroll support for drum pickers ───────────────
function addDrumSwipe(elId, callback) {
  const el = document.getElementById(elId);
  if (!el) return;
  let startY = null;
  el.addEventListener('touchstart', e => { startY = e.touches[0].clientY; }, { passive: true });
  el.addEventListener('touchend', e => {
    if (startY === null) return;
    const dy = startY - e.changedTouches[0].clientY;
    if (Math.abs(dy) > 10) callback(dy > 0 ? 1 : -1);
    startY = null;
  }, { passive: true });
  el.addEventListener('wheel', e => {
    e.preventDefault();
    callback(e.deltaY > 0 ? 1 : -1);
  }, { passive: false });
}
