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
  // Set the message text on the hidden source element BEFORE openModal clones it
  const srcMsg = document.getElementById('unlink-msg-' + gid);
  if (srcMsg) srcMsg.textContent = `Remove link to "${ename}" from this goal?`;
  openModal('modal-unlink-' + gid);
  // Also set it in the cloned active-modal in case it was already open
  const activeMsg = document.querySelector('#active-modal #unlink-msg-' + gid)
                 || document.querySelector('#active-modal p');
  if (activeMsg) activeMsg.textContent = `Remove link to "${ename}" from this goal?`;
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


/* ══════════════════════════════════════════════════
   ROADMAP SYSTEM  ─  Snake-level game-style UI
   ══════════════════════════════════════════════════ */

let _rmGoalId   = null;
let _rmEditSid  = null;
let _rmData     = null;

// ── Open roadmap panel ──────────────────────────────
function openRoadmap(gid, goalTitle) {
  _rmGoalId = gid;
  const old = document.getElementById('roadmap-overlay');
  if (old) old.remove();
  _injectRoadmapHtml(gid, goalTitle);
  if (!window.history.state || window.history.state.roadmapOpen !== gid) {
    window.history.pushState({ roadmapOpen: gid, roadmapTitle: goalTitle }, '', '#roadmap-' + gid);
  }
}

function _injectRoadmapHtml(gid, goalTitle) {
  const div = document.createElement('div');
  div.id = 'roadmap-overlay';
  div.className = 'roadmap-overlay';
  div.innerHTML = _roadmapHtmlTemplate();
  document.body.appendChild(div);
  document.body.style.overflow = 'hidden';
  div.addEventListener('click', function(e) {
    if (e.target === div) closeRoadmapPanel();
  });
  const titleEl = document.getElementById('rm-goal-title');
  if (titleEl) titleEl.textContent = goalTitle || 'Goal Roadmap';
  _loadRoadmap(gid);
}

function _roadmapHtmlTemplate() {
  return `
  <div class="roadmap-panel" id="roadmap-panel">

    <!-- Header -->
    <div class="roadmap-header">
      <div class="roadmap-header-left">
        <div class="roadmap-icon-ring">🗺</div>
        <div>
          <div class="roadmap-header-label">ROADMAP</div>
          <div class="roadmap-header-title" id="rm-goal-title">Loading…</div>
        </div>
      </div>
      <div class="roadmap-header-right">
        <div class="rm-progress-pill" id="rm-progress-pill">
          <span id="rm-pill-done">0</span><span class="rm-pill-sep">/</span><span id="rm-pill-total">0</span>
        </div>
        <button class="rm-action-btn rm-edit-roadmap-btn" onclick="openRmEditRoadmap()" title="Edit Roadmap">
          <svg viewBox="0 0 18 18" fill="none"><path d="M13 2.5l2.5 2.5-9 9-3 .5.5-3 9-9z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="rm-action-btn rm-delete-roadmap-btn" onclick="confirmDeleteAllStages()" title="Delete All Stages">
          <svg viewBox="0 0 18 18" fill="none"><polyline points="3,5 15,5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M7 5V3h4v2M6 5v9a1 1 0 001 1h4a1 1 0 001-1V5H6z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="roadmap-close-btn" onclick="closeRoadmapPanel()" aria-label="Close">✕</button>
      </div>
    </div>

    <!-- Progress track -->
    <div class="rm-progress-track-wrap" id="rm-progress-track-wrap">
      <div class="rm-progress-bar-bg">
        <div class="rm-progress-bar-fill" id="rm-progress-bar-fill"></div>
      </div>
      <div class="rm-progress-ticks" id="rm-progress-ticks"></div>
    </div>

    <!-- Stats Bar -->
    <div class="roadmap-stats-bar" id="rm-stats-bar">
      <div class="roadmap-stat">
        <span class="roadmap-stat-num" id="rm-stat-total">0</span>
        <span class="roadmap-stat-lbl">Total</span>
      </div>
      <div class="roadmap-stat-divider"></div>
      <div class="roadmap-stat">
        <span class="roadmap-stat-num rm-stat-done" id="rm-stat-done">0</span>
        <span class="roadmap-stat-lbl">Completed</span>
      </div>
      <div class="roadmap-stat-divider"></div>
      <div class="roadmap-stat">
        <span class="roadmap-stat-num rm-stat-rem" id="rm-stat-remaining">0</span>
        <span class="roadmap-stat-lbl">Remaining</span>
      </div>
      <div class="roadmap-stat-divider"></div>
      <div class="roadmap-stat roadmap-stat-pct">
        <span class="roadmap-stat-num rm-stat-pct" id="rm-stat-pct">0%</span>
        <span class="roadmap-stat-lbl">Progress</span>
      </div>
    </div>

    <!-- Exam Link bar -->
    <div class="rm-exam-link-bar" id="rm-exam-link-bar" style="display:none">
      <div class="rm-exam-link-inner" id="rm-exam-link-inner"></div>
    </div>

    <!-- Add Stage Form -->
    <div class="roadmap-add-form" id="rm-add-form">
      <div class="roadmap-add-fields">
        <input type="text" id="rm-new-stage-title" class="roadmap-input" placeholder="Add new stage…" maxlength="120"
               onkeydown="if(event.key==='Enter'){event.preventDefault();addRoadmapStage()}"/>
        <input type="text" id="rm-new-stage-desc"  class="roadmap-input roadmap-input-desc" placeholder="Optional description…" maxlength="250"
               onkeydown="if(event.key==='Enter'){event.preventDefault();addRoadmapStage()}"/>
      </div>
      <button class="roadmap-add-btn" onclick="addRoadmapStage()">
        <span>+</span> Add Stage
      </button>
    </div>

    <!-- Snake Roadmap stages -->
    <div class="roadmap-stages-wrap" id="rm-stages-wrap">
      <div class="roadmap-empty-state" id="rm-empty-state" style="display:none">
        <div class="roadmap-empty-icon">🚀</div>
        <div class="roadmap-empty-title">No stages yet</div>
        <div class="roadmap-empty-sub">Add your first stage to start mapping your journey</div>
      </div>
      <div class="rm-snake-road" id="rm-snake-road"></div>
    </div>
  </div>

  <!-- Single-stage edit modal -->
  <div id="rm-edit-modal" class="rm-edit-modal hidden">
    <div class="rm-edit-box">
      <div class="rm-edit-header">
        <span>Edit Stage</span>
        <button onclick="closeRmEditModal()">✕</button>
      </div>
      <input type="text" id="rm-edit-title" class="roadmap-input" placeholder="Stage title…" maxlength="120"
             onkeydown="if(event.key==='Enter'){saveRmEdit()}"/>
      <input type="text" id="rm-edit-desc"  class="roadmap-input roadmap-input-desc" placeholder="Description…" maxlength="250"
             onkeydown="if(event.key==='Enter'){saveRmEdit()}"/>
      <div class="rm-edit-actions">
        <button class="btn-secondary" onclick="closeRmEditModal()">Cancel</button>
        <button class="btn-primary"   onclick="saveRmEdit()">Save</button>
      </div>
    </div>
  </div>

  <!-- Full roadmap edit modal (Edit Roadmap button) -->
  <div id="rm-all-edit-modal" class="rm-edit-modal hidden">
    <div class="rm-edit-box rm-all-edit-box">
      <div class="rm-edit-header">
        <span>✏ Edit Roadmap</span>
        <button onclick="closeRmAllEditModal()">✕</button>
      </div>
      <div class="rm-all-edit-body" id="rm-all-edit-body">
        <div class="rm-all-edit-loading">Loading stages…</div>
      </div>
      <div class="rm-edit-actions">
        <button class="btn-secondary" onclick="closeRmAllEditModal()">Close</button>
        <button class="btn-primary" onclick="saveAllRmEdits()">Save All Changes</button>
      </div>
    </div>
  </div>

  <!-- Delete all confirmation modal -->
  <div id="rm-delete-all-modal" class="rm-edit-modal hidden">
    <div class="rm-edit-box rm-delete-all-box">
      <div class="rm-edit-header">
        <span>🗑 Delete All Stages?</span>
        <button onclick="document.getElementById('rm-delete-all-modal').classList.add('hidden')">✕</button>
      </div>
      <p class="rm-delete-all-msg">This will permanently delete all roadmap stages. This cannot be undone.</p>
      <div class="rm-edit-actions">
        <button class="btn-secondary" onclick="document.getElementById('rm-delete-all-modal').classList.add('hidden')">Cancel</button>
        <button class="btn-danger" onclick="deleteAllRmStages()">Delete All</button>
      </div>
    </div>
  </div>
  `;
}

// ── Close panel ──────────────────────────────────────────
function closeRoadmapPanel() {
  const ov = document.getElementById('roadmap-overlay');
  if (!ov) return;
  const panel = document.getElementById('roadmap-panel');
  if (panel) panel.style.animation = 'rmPanelOut 0.28s cubic-bezier(0.4,0,1,1) both';
  ov.style.animation = 'rmOverlayOut 0.28s ease both';
  const styleId = 'rm-out-kf';
  if (!document.getElementById(styleId)) {
    const s = document.createElement('style');
    s.id = styleId;
    s.textContent = `
      @keyframes rmPanelOut  { from{transform:translateX(0);opacity:1} to{transform:translateX(100%);opacity:.4} }
      @keyframes rmOverlayOut{ from{opacity:1} to{opacity:0} }
    `;
    document.head.appendChild(s);
  }
  if (window.location.hash && window.location.hash.startsWith('#roadmap-')) {
    window.history.pushState(null, '', window.location.pathname + window.location.search);
  }
  setTimeout(() => {
    ov.remove();
    document.body.style.overflow = '';
    _rmGoalId = null;
    _rmData   = null;
  }, 300);
}

function closeRoadmapOverlay(e) {
  if (e && e.target && e.target.id === 'roadmap-overlay') closeRoadmapPanel();
}

window.addEventListener('popstate', function(e) {
  const ov = document.getElementById('roadmap-overlay');
  if (ov) {
    const panel = document.getElementById('roadmap-panel');
    if (panel) panel.style.animation = 'rmPanelOut 0.28s cubic-bezier(0.4,0,1,1) both';
    ov.style.animation = 'rmOverlayOut 0.28s ease both';
    setTimeout(() => {
      ov.remove();
      document.body.style.overflow = '';
      _rmGoalId = null;
      _rmData   = null;
    }, 300);
  } else if (e.state && e.state.roadmapOpen) {
    openRoadmap(e.state.roadmapOpen, e.state.roadmapTitle || '');
  }
});

// ── Load data ─────────────────────────────────────
function _loadRoadmap(gid) {
  fetch(`/roadmap/${gid}`)
    .then(r => r.json())
    .then(d => {
      _rmData = d;
      _renderRoadmap(d);
      _loadRoadmapExams(gid);
    })
    .catch(() => showToast('Error loading roadmap', 'error'));
}

// ── Load & render exam link bar ─────
function _loadRoadmapExams(gid) {
  fetch(`/roadmap/${gid}/exam-info`)
    .then(r => r.json())
    .then(d => {
      const bar = document.getElementById('rm-exam-link-bar');
      const inner = document.getElementById('rm-exam-link-inner');
      if (!bar || !inner) return;
      bar.style.display = 'flex';

      // ── Left group: label + exam pills (anchored left) ──
      let leftHtml = '<span class="rm-exam-link-label">Exam</span>';
      if (d.linked && d.linked.length > 0) {
        d.linked.forEach(ex => {
          leftHtml += `<span class="rm-exam-pill" id="rm-ex-pill-${ex.id}">
            <span class="rm-exam-pill-dot"></span>
            <span class="rm-exam-pill-name">${_escHtml(ex.name)}</span>
            <button class="rm-exam-pill-unlink" onclick="rmUnlinkExam(${gid},${ex.id},'${_escAttr(ex.name)}')" title="Unlink">✕</button>
          </span>`;
        });
      } else {
        leftHtml += '<span class="rm-exam-none-label">No exam linked</span>';
      }

      // ── Right group: select + Link button (anchored right) ──
      let rightHtml = '';
      if (d.available && d.available.length > 0) {
        rightHtml = `<div class="rm-exam-link-select-wrap">
          <select id="rm-exam-select-${gid}" class="rm-exam-select">
            <option value="">Select exam…</option>
            ${d.available.map(ex => `<option value="${ex.id}">${_escHtml(ex.name)}</option>`).join('')}
          </select>
          <button class="rm-exam-link-btn" onclick="rmLinkExam(${gid})">
            <svg viewBox="0 0 16 16" fill="none" width="12" height="12" style="flex-shrink:0"><path d="M6.5 9.5a4 4 0 005.656-5.656L10.5 2.188A4 4 0 004.844 7.844" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M9.5 6.5a4 4 0 00-5.656 5.656l1.656 1.656A4 4 0 0011.156 8.156" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            Link Exam
          </button>
        </div>`;
      }

      inner.innerHTML = `<div class="rm-exam-left-group">${leftHtml}</div>${rightHtml}`;
    })
    .catch(() => {});
}

function rmLinkExam(gid) {
  const sel = document.getElementById(`rm-exam-select-${gid}`);
  if (!sel || !sel.value) { showToast('Select an exam first', 'warn'); return; }
  const fd = new FormData();
  fd.append('exam_id', sel.value);
  fetch(`/link-exam-to-goal/${gid}`, {method:'POST', body:fd})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        showToast('Exam linked ✓', 'success');
        _loadRoadmapExams(gid);
        setTimeout(() => { if (!document.getElementById('roadmap-overlay')) location.reload(); }, 100);
      } else { showToast(d.msg || 'Error linking', 'error'); }
    });
}

function rmUnlinkExam(gid, eid, ename) {
  if (!confirm(`Unlink "${ename}" from this goal?`)) return;
  const pill = document.getElementById(`rm-ex-pill-${eid}`);
  if (pill) { pill.style.opacity='0'; pill.style.transform='scale(0.8)'; pill.style.transition='all 0.25s'; }
  setTimeout(() => {
    fetch(`/unlink-exam-from-goal/${gid}/${eid}`, {method:'POST'})
      .then(r => r.json())
      .then(() => { showToast('Exam unlinked', 'success'); _loadRoadmapExams(gid); });
  }, 250);
}

// ── Render ────────────────────────────────────────
function _renderRoadmap(d) {
  _el('rm-stat-total',     d.total || 0);
  _el('rm-stat-done',      d.done  || 0);
  _el('rm-stat-remaining', d.remaining || 0);
  _el('rm-stat-pct',       (d.pct || 0) + '%');
  _el('rm-pill-done',      d.done  || 0);
  _el('rm-pill-total',     d.total || 0);
  _updateProgressBar(d.pct || 0, d.done || 0, d.total || 0);

  const empty = document.getElementById('rm-empty-state');
  const snake = document.getElementById('rm-snake-road');
  if (!d.stages || d.stages.length === 0) {
    if (empty) empty.style.display = 'flex';
    if (snake) snake.innerHTML = '';
    return;
  }
  if (empty) empty.style.display = 'none';
  if (snake) {
    snake.innerHTML = '';
    _buildSnakeRoad(snake, d.stages, d.active_idx);
  }
}

function _el(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function _updateProgressBar(pct, done, total) {
  const fill  = document.getElementById('rm-progress-bar-fill');
  const ticks = document.getElementById('rm-progress-ticks');
  if (fill) fill.style.width = Math.min(pct, 100) + '%';
  if (ticks && total > 0) {
    ticks.innerHTML = '';
    for (let i = 0; i < total; i++) {
      const tick = document.createElement('div');
      tick.className = 'rm-tick' + (i < done ? ' rm-tick-done' : i === done ? ' rm-tick-active' : '');
      tick.innerHTML = i < done
        ? '<svg viewBox="0 0 12 12" fill="none"><polyline points="2,6 5,9 10,3" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        : '';
      tick.style.left = ((i / total) * 100) + '%';
      ticks.appendChild(tick);
    }
  }
}

// ── Snake Road Builder — single-column vertical snake ────────────────────────
function _buildSnakeRoad(container, stages, activeIdx) {
  stages.forEach((s, absIdx) => {
    const isDone   = s.completed;
    const isActive = absIdx === activeIdx && !isDone;
    const isLast   = absIdx === stages.length - 1;

    // Determine if next stage is done (for connector colour)
    const nextStage = stages[absIdx + 1];
    const connDone  = isDone && nextStage && nextStage.completed;
    const connColor = connDone ? 'var(--emerald)' : 'var(--violet)';

    // ── Stage row wrapper ──
    const stageRow = document.createElement('div');
    stageRow.className = 'rm-stage-row';
    stageRow.id = 'rm-stage-' + s.id;
    stageRow.style.animationDelay = (absIdx * 55) + 'ms';

    // Circle state
    let circleClass = 'rm-node-circle';
    if (isDone)   circleClass += ' rm-circle-done';
    if (isActive) circleClass += ' rm-circle-active';

    const completedAt = s.completed_at
      ? new Date(s.completed_at).toLocaleDateString('en-IN', {day:'numeric', month:'short'})
      : '';

    let statusBadge = '';
    if (isDone)        statusBadge = `<span class="rm-card-status rm-status-done">✓ Done${completedAt ? ' · ' + completedAt : ''}</span>`;
    else if (isActive) statusBadge = `<span class="rm-card-status rm-status-active">▶ Active</span>`;
    else               statusBadge = `<span class="rm-card-status rm-status-pending">Stage ${absIdx + 1}</span>`;

    stageRow.innerHTML = `
      <div class="rm-stage-card ${isDone ? 'rm-card-done' : ''} ${isActive ? 'rm-card-active' : ''}">
        <button class="${circleClass}" onclick="toggleRmStage(${s.id})" title="Toggle completion" aria-label="Mark stage ${absIdx+1} complete">
          <span class="rm-cn-num">${absIdx + 1}</span>
          <span class="rm-cn-tick">
            <svg viewBox="0 0 20 20" fill="none"><polyline points="4,10 8,14 16,6" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </span>
          <span class="rm-cn-dot"></span>
        </button>
        <div class="rm-card-body">
          ${statusBadge}
          <div class="rm-card-title ${isDone ? 'rm-card-title-done' : ''}">${_escHtml(s.title)}</div>
          ${s.description ? `<div class="rm-card-desc">${_escHtml(s.description)}</div>` : ''}
        </div>
      </div>
    `;

    container.appendChild(stageRow);

    // ── Vertical connector to next stage ──
    if (!isLast) {
      const conn = document.createElement('div');
      conn.className = 'rm-v-connector' + (connDone ? ' rm-vc-done' : '');
      conn.setAttribute('aria-hidden', 'true');
      conn.innerHTML = `
        <svg viewBox="0 0 20 48" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">
          <line x1="10" y1="2" x2="10" y2="46"
            stroke="${connColor}"
            stroke-width="2.2"
            stroke-dasharray="5 4"
            stroke-linecap="round"
            class="rm-vc-line ${connDone ? 'rm-vc-line-done' : 'rm-vc-line-pending'}"/>
        </svg>`;
      container.appendChild(conn);
    }
  });
}

// ── Toggle stage completion ─────────────────────────
function toggleRmStage(sid) {
  if (!_rmGoalId) return;
  const circle = document.querySelector(`#rm-stage-${sid} .rm-node-circle`);
  if (circle) circle.classList.add('rm-completing');
  fetch(`/roadmap/${_rmGoalId}/toggle-stage/${sid}`, {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        _loadRoadmap(_rmGoalId);
        showToast(d.completed ? '✓ Stage completed!' : 'Stage marked pending', d.completed ? 'success' : 'info');
      }
    })
    .catch(() => showToast('Error updating stage', 'error'));
}

// ── Add stage ──────────────────────────────────────
function addRoadmapStage() {
  const titleEl = document.getElementById('rm-new-stage-title');
  const descEl  = document.getElementById('rm-new-stage-desc');
  if (!titleEl) return;
  const title = titleEl.value.trim();
  if (!title) { titleEl.focus(); showToast('Enter a stage title', 'warn'); return; }
  const desc = descEl ? descEl.value.trim() : '';
  fetch(`/roadmap/${_rmGoalId}/add-stage`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, description: desc})
  })
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        titleEl.value = '';
        if (descEl) descEl.value = '';
        _loadRoadmap(_rmGoalId);
        showToast('Stage added', 'success');
      } else {
        showToast(d.msg || 'Error adding stage', 'error');
      }
    })
    .catch(() => showToast('Error adding stage', 'error'));
}

// ── Single stage edit (called from Edit Roadmap modal) ──
function openRmEdit(sid, currentTitle, currentDesc) {
  _rmEditSid = sid;
  const titleEl = document.getElementById('rm-edit-title');
  const descEl  = document.getElementById('rm-edit-desc');
  if (titleEl) titleEl.value = currentTitle || '';
  if (descEl)  descEl.value  = currentDesc  || '';
  const modal = document.getElementById('rm-edit-modal');
  if (modal) {
    modal.classList.remove('hidden');
    if (titleEl) { titleEl.focus(); titleEl.select(); }
  }
}
function closeRmEditModal() {
  const modal = document.getElementById('rm-edit-modal');
  if (modal) modal.classList.add('hidden');
  _rmEditSid = null;
}
function saveRmEdit() {
  if (!_rmEditSid || !_rmGoalId) return;
  const titleEl = document.getElementById('rm-edit-title');
  const descEl  = document.getElementById('rm-edit-desc');
  const title   = titleEl ? titleEl.value.trim() : '';
  if (!title) { if (titleEl) titleEl.focus(); showToast('Title required', 'warn'); return; }
  const desc = descEl ? descEl.value.trim() : '';
  fetch(`/roadmap/${_rmGoalId}/edit-stage/${_rmEditSid}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, description: desc})
  })
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        closeRmEditModal();
        _loadRoadmap(_rmGoalId);
        // Also refresh the all-edit modal if it's open
        const allModal = document.getElementById('rm-all-edit-modal');
        if (allModal && !allModal.classList.contains('hidden')) _populateAllEditModal();
        showToast('Stage updated', 'success');
      } else {
        showToast(d.msg || 'Error saving', 'error');
      }
    })
    .catch(() => showToast('Error saving stage', 'error'));
}

// ── Full Roadmap Edit Modal ─────────────────────────
function openRmEditRoadmap() {
  const modal = document.getElementById('rm-all-edit-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  _populateAllEditModal();
}
function closeRmAllEditModal() {
  const modal = document.getElementById('rm-all-edit-modal');
  if (modal) modal.classList.add('hidden');
}

function _populateAllEditModal() {
  const body = document.getElementById('rm-all-edit-body');
  if (!body || !_rmData) return;
  const stages = _rmData.stages || [];
  if (stages.length === 0) {
    body.innerHTML = '<div class="rm-all-edit-loading">No stages yet. Add stages below.</div>';
    return;
  }
  body.innerHTML = stages.map((s, i) => `
    <div class="rm-all-edit-row" id="rm-aer-${s.id}">
      <div class="rm-aer-num">${i + 1}</div>
      <div class="rm-aer-fields">
        <input type="text" class="roadmap-input rm-aer-title" data-sid="${s.id}"
               value="${_escHtml(s.title)}" placeholder="Stage title…" maxlength="120"/>
        <input type="text" class="roadmap-input rm-aer-desc" data-sid="${s.id}"
               value="${_escHtml(s.description || '')}" placeholder="Description (optional)…" maxlength="250"/>
      </div>
      <button class="rm-aer-delete" onclick="deleteRmStageFromModal(${s.id})" title="Delete stage">
        <svg viewBox="0 0 16 16" fill="none"><polyline points="2,4 14,4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M5 4V3h6v1M4 4v9a1 1 0 001 1h6a1 1 0 001-1V4H4z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  `).join('');
}

function saveAllRmEdits() {
  const body = document.getElementById('rm-all-edit-body');
  if (!body || !_rmGoalId) return;
  const rows = body.querySelectorAll('.rm-all-edit-row');
  if (rows.length === 0) { closeRmAllEditModal(); return; }

  // Collect all edits
  const edits = [];
  let hasError = false;
  rows.forEach(row => {
    const titleEl = row.querySelector('.rm-aer-title');
    const descEl  = row.querySelector('.rm-aer-desc');
    const sid = parseInt(titleEl ? titleEl.dataset.sid : 0);
    const title = titleEl ? titleEl.value.trim() : '';
    const desc  = descEl  ? descEl.value.trim()  : '';
    if (!title) {
      titleEl && titleEl.focus();
      showToast('All stages must have a title', 'warn');
      hasError = true;
      return;
    }
    edits.push({sid, title, desc});
  });
  if (hasError) return;

  // Save each edit sequentially
  const btn = document.querySelector('#rm-all-edit-modal .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

  Promise.all(edits.map(e =>
    fetch(`/roadmap/${_rmGoalId}/edit-stage/${e.sid}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title: e.title, description: e.desc})
    }).then(r => r.json())
  ))
  .then(results => {
    const failed = results.filter(r => r.status !== 'ok');
    if (failed.length === 0) {
      showToast('All stages saved ✓', 'success');
      closeRmAllEditModal();
      _loadRoadmap(_rmGoalId);
    } else {
      showToast(`${failed.length} stage(s) failed to save`, 'error');
    }
  })
  .catch(() => showToast('Error saving stages', 'error'))
  .finally(() => {
    if (btn) { btn.disabled = false; btn.textContent = 'Save All Changes'; }
  });
}

function deleteRmStageFromModal(sid) {
  if (!_rmGoalId) return;
  const row = document.getElementById('rm-aer-' + sid);
  if (row) { row.style.opacity = '0'; row.style.transform = 'scale(0.95)'; row.style.transition = 'all 0.2s'; }
  setTimeout(() => {
    fetch(`/roadmap/${_rmGoalId}/delete-stage/${sid}`, {method: 'POST'})
      .then(r => r.json())
      .then(d => {
        if (d.status === 'ok') {
          if (row) row.remove();
          _loadRoadmap(_rmGoalId);
          showToast('Stage deleted', 'success');
          // refresh the edit modal data
          fetch(`/roadmap/${_rmGoalId}`)
            .then(r => r.json())
            .then(data => { _rmData = data; _populateAllEditModal(); });
        }
      })
      .catch(() => showToast('Error deleting stage', 'error'));
  }, 200);
}

// ── Delete stage (legacy, used from edit modal row) ──
function deleteRmStage(sid) {
  if (!confirm('Delete this stage?')) return;
  fetch(`/roadmap/${_rmGoalId}/delete-stage/${sid}`, {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.status === 'ok') {
        const card = document.getElementById('rm-stage-' + sid);
        if (card) {
          card.style.animation = 'rmStageOut 0.28s ease both';
          const s = document.createElement('style');
          s.textContent = '@keyframes rmStageOut{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(0.85)}}';
          document.head.appendChild(s);
          setTimeout(() => { _loadRoadmap(_rmGoalId); }, 280);
        } else {
          _loadRoadmap(_rmGoalId);
        }
        showToast('Stage deleted', 'success');
      }
    })
    .catch(() => showToast('Error deleting stage', 'error'));
}

// ── Delete ALL stages confirm flow ─────────────────
function confirmDeleteAllStages() {
  const modal = document.getElementById('rm-delete-all-modal');
  if (modal) modal.classList.remove('hidden');
}
function deleteAllRmStages() {
  if (!_rmGoalId || !_rmData) return;
  const stages = (_rmData.stages || []).slice();
  const modal = document.getElementById('rm-delete-all-modal');
  if (modal) modal.classList.add('hidden');
  if (stages.length === 0) return;

  const btn = document.querySelector('#rm-delete-all-modal .btn-danger');
  if (btn) btn.disabled = true;

  Promise.all(stages.map(s =>
    fetch(`/roadmap/${_rmGoalId}/delete-stage/${s.id}`, {method: 'POST'}).then(r => r.json())
  ))
  .then(() => {
    _loadRoadmap(_rmGoalId);
    showToast('All stages deleted', 'success');
  })
  .catch(() => showToast('Error deleting stages', 'error'));
}

function _escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function _escAttr(s) {
  return String(s || '').replace(/'/g,"\\'").replace(/"/g,'\\"');
}

// ── Keyboard close ─────────────────────────────────
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && document.getElementById('roadmap-overlay')) {
    const allEditModal = document.getElementById('rm-all-edit-modal');
    const editModal    = document.getElementById('rm-edit-modal');
    const delModal     = document.getElementById('rm-delete-all-modal');
    if (allEditModal && !allEditModal.classList.contains('hidden')) {
      closeRmAllEditModal();
    } else if (editModal && !editModal.classList.contains('hidden')) {
      closeRmEditModal();
    } else if (delModal && !delModal.classList.contains('hidden')) {
      delModal.classList.add('hidden');
    } else {
      closeRoadmapPanel();
    }
  }
});

