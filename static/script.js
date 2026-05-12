/* ══════════════════════════════════════════════════
   AURIX — Main JS  (Dark Theme Only)
   ══════════════════════════════════════════════════ */

// Always dark theme
document.documentElement.setAttribute('data-theme', 'dark');

// ─── CINEMATIC SPLASH — 30 seconds, Canvas-based ─────────
// Phase 1 (0-3s): Absolute darkness
// Phase 2 (3-8s): Particle emergence from void
// Phase 3 (8-15s): Energy convergence toward center
// Phase 4 (15-20s): Core formation & pulsation
// Phase 5 (20-24s): SHOCKWAVE EVENT
// Phase 6 (24-28s): Brand reveal — AURIX
// Phase 7 (28-30s): Stabilization
// Phase 8: Smooth fade → dashboard

const SPLASH_DURATION = 30000;
let splashDone = false;
let splashAnimId = null;

// Splash audio removed — silent cinematic splash
function startSplashAudio() { /* no-op */ }
function stopSplashAudio()  { /* no-op */ }



function exitSplash() {
  if (splashDone) return;
  splashDone = true;
  // Mark splash as shown — internal navigation will skip it
  sessionStorage.setItem('aurix_splash_done', '1');
  if (splashAnimId) cancelAnimationFrame(splashAnimId);

  // Fade out audio gracefully (only needed if Skip pressed early)
  stopSplashAudio();

  const splashScreen = document.getElementById('splash-screen');
  const mainApp      = document.getElementById('main-app');

  // Fade out splash
  if (splashScreen) {
    splashScreen.style.transition = 'opacity 0.9s cubic-bezier(0.4,0,1,1)';
    splashScreen.style.opacity = '0';
    splashScreen.style.pointerEvents = 'none';
  }

  // Reveal main app simultaneously so there is no black gap
  if (mainApp) {
    mainApp.style.display = 'block';
  }
  document.body.style.overflow = '';

  // Remove splash from layout after fade completes
  setTimeout(() => {
    if (splashScreen) splashScreen.style.display = 'none';
  }, 950);
}

// ─── REPLAY SPLASH (topbar button / Ctrl+S) ───────────
function replaySplash() {
  const splashScreen = document.getElementById('splash-screen');
  if (!splashScreen) return;

  if (splashAnimId) { cancelAnimationFrame(splashAnimId); splashAnimId = null; }
  splashDone = false;

  const prog = document.getElementById('splash-progress');
  if (prog) prog.style.width = '0%';
  const nameEl = document.getElementById('splash-name');
  const subEl  = document.getElementById('splash-sub');
  if (nameEl) nameEl.classList.remove('visible');
  if (subEl)  subEl.classList.remove('visible');

  splashScreen.style.transition = '';
  splashScreen.style.opacity = '1';
  splashScreen.style.pointerEvents = '';
  splashScreen.style.display = 'block';
  const splashEl = document.getElementById('splash');
  if (splashEl) splashEl.classList.add('splash-active');
  document.body.style.overflow = 'hidden';

  cinematicSplash();
}

function cinematicSplash() {
  const el = document.getElementById('splash');
  const canvas = document.getElementById('splash-canvas');
  if (!el || !canvas) return;

  // Start synchronized audio soundtrack
  startSplashAudio();

  const ctx = canvas.getContext('2d');
  let W = canvas.width  = window.innerWidth;
  let H = canvas.height = window.innerHeight;
  window.addEventListener('resize', () => {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  });

  const isMobile = window.innerWidth < 768;
  const PARTICLE_COUNT = isMobile ? 120 : 280;

  // ── Phase 2: Void particles ──────────────────────────────
  const voidParticles = Array.from({length: PARTICLE_COUNT}, () => ({
    x: Math.random() * W,
    y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.2 + 0.3,
    alpha: Math.random() * 0.4 + 0.05,
    hue: 200 + Math.random() * 60
  }));

  // ── Shockwave state ──────────────────────────────────────
  let shockwaveFired = false;
  let shockwaveR = 0;
  let shockwaveAlpha = 0;

  // ── Ripple ring state ────────────────────────────────────
  let rings = [];

  const startTime = performance.now();

  function easeInOut(t) { return t < 0.5 ? 2*t*t : -1+(4-2*t)*t; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function fade(elapsed, fadeIn, fullStart, fullEnd, fadeOut) {
    if (elapsed < fadeIn) return 0;
    if (elapsed < fullStart) return (elapsed - fadeIn) / (fullStart - fadeIn);
    if (elapsed < fullEnd)   return 1;
    if (elapsed < fadeOut)   return 1 - (elapsed - fullEnd) / (fadeOut - fullEnd);
    return 0;
  }

  function draw(now) {
    const elapsed = now - startTime;
    const cx = W / 2, cy = H / 2;

    // Progress bar
    const prog = document.getElementById('splash-progress');
    if (prog) prog.style.width = (Math.min(elapsed / SPLASH_DURATION, 1) * 100) + '%';

    // ── Background: hold pure black until phase 3 ───────────
    const bgAlpha = elapsed < 200 ? 1 : (elapsed < 8000 ? 0.25 : 0.15);
    ctx.fillStyle = `rgba(0,0,2,${bgAlpha})`;
    ctx.fillRect(0, 0, W, H);

    // ── Phase 1: Pure darkness 0–3s (nothing drawn) ─────────
    if (elapsed < 3000) {
      splashAnimId = requestAnimationFrame(draw);
      return;
    }

    // ── Phase 2: Particle emergence (3–8s) ──────────────────
    const p2Alpha = clamp((elapsed - 3000) / 3000, 0, 1);

    voidParticles.forEach(p => {
      // In phase 3+, particles move toward center
      if (elapsed > 8000) {
        const dx = cx - p.x, dy = cy - p.y;
        const dist = Math.sqrt(dx*dx + dy*dy) + 0.01;
        const convergeForce = clamp((elapsed - 8000) / 12000, 0, 1);
        const speedMult = elapsed > 18000 ? (1 + (elapsed - 18000) / 3000 * 4) : 1;
        p.vx += (dx / dist) * 0.08 * convergeForce * speedMult;
        p.vy += (dy / dist) * 0.08 * convergeForce * speedMult;
        // Friction
        p.vx *= 0.97;
        p.vy *= 0.97;
      }
      p.x += p.vx;
      p.y += p.vy;

      // If shockwave fired, push particles outward
      if (shockwaveFired && elapsed < 27000) {
        const dx = p.x - cx, dy = p.y - cy;
        const dist = Math.sqrt(dx*dx + dy*dy) + 1;
        const pushForce = Math.max(0, 1 - (elapsed - 20000) / 4000) * 3;
        p.vx += (dx / dist) * pushForce;
        p.vy += (dy / dist) * pushForce;
      }

      // Wrap edges
      if (p.x < -10) p.x = W + 10;
      if (p.x > W + 10) p.x = -10;
      if (p.y < -10) p.y = H + 10;
      if (p.y > H + 10) p.y = -10;

      const visAlpha = p2Alpha * p.alpha * (elapsed > 27000 ? clamp(1 - (elapsed - 27000) / 2000, 0, 1) : 1);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue},70%,70%,${visAlpha})`;
      ctx.fill();
    });

    // ── Phase 4: Core formation (15–20s) ────────────────────
    if (elapsed > 12000) {
      const coreAlpha = clamp((elapsed - 12000) / 5000, 0, 1);
      const pulseFreq = 0.8 + (elapsed > 17000 ? (elapsed - 17000) / 1000 * 0.5 : 0);
      const pulse = 1 + 0.08 * Math.sin(elapsed * 0.001 * pulseFreq * Math.PI * 2);
      const coreR = (elapsed > 20000 ? Math.max(0, 30 - (elapsed - 20000) / 200) : 30) * pulse;
      const outerR = coreR * 2.5;

      if (!shockwaveFired && coreR > 1) {
        // Outer glow halo
        const halo = ctx.createRadialGradient(cx, cy, coreR * 0.5, cx, cy, outerR);
        halo.addColorStop(0, `rgba(120,130,255,${coreAlpha * 0.35})`);
        halo.addColorStop(0.5, `rgba(80,100,220,${coreAlpha * 0.1})`);
        halo.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.beginPath();
        ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
        ctx.fillStyle = halo;
        ctx.fill();
        // Core bright center
        const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
        coreGrad.addColorStop(0, `rgba(255,255,255,${coreAlpha * 0.9})`);
        coreGrad.addColorStop(0.3, `rgba(160,170,255,${coreAlpha * 0.7})`);
        coreGrad.addColorStop(0.7, `rgba(80,100,220,${coreAlpha * 0.4})`);
        coreGrad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.beginPath();
        ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
        ctx.fillStyle = coreGrad;
        ctx.fill();
      }
    }

    // ── Phase 5: SHOCKWAVE (20–24s) ─────────────────────────
    if (elapsed > 20000 && !shockwaveFired) {
      shockwaveFired = true;
      shockwaveR = 0;
      rings = [];
    }
    if (shockwaveFired) {
      const shockElapsed = elapsed - 20000;
      shockwaveR = shockElapsed * 0.9 + shockElapsed * shockElapsed * 0.00015;
      shockwaveAlpha = Math.max(0, 1 - shockElapsed / 4000);

      // Add trailing rings every 100ms
      if (shockElapsed < 3000 && Math.floor(shockElapsed / 100) > rings.length) {
        rings.push({ r: shockwaveR, born: elapsed });
      }

      // Draw rings with distortion effect
      rings.forEach(ring => {
        const ringAge = elapsed - ring.born;
        const ringAlpha = Math.max(0, 0.6 - ringAge / 2000) * shockwaveAlpha;
        if (ringAlpha > 0.005) {
          ctx.beginPath();
          ctx.arc(cx, cy, ring.r + (elapsed - ring.born) * 0.08, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(160,170,255,${ringAlpha * 0.7})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });

      // Primary shockwave ring
      if (shockwaveAlpha > 0.01) {
        ctx.beginPath();
        ctx.arc(cx, cy, shockwaveR, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(200,210,255,${shockwaveAlpha * 0.9})`;
        ctx.lineWidth = clamp(4 - shockElapsed * 0.001, 1, 4);
        ctx.stroke();

        // Distortion ripple lines — subtle radial streaks
        for (let i = 0; i < 12; i++) {
          const angle = (i / 12) * Math.PI * 2;
          const innerR = shockwaveR * 0.85;
          const outerR2 = shockwaveR * 1.05;
          ctx.beginPath();
          ctx.moveTo(cx + Math.cos(angle) * innerR, cy + Math.sin(angle) * innerR);
          ctx.lineTo(cx + Math.cos(angle) * outerR2, cy + Math.sin(angle) * outerR2);
          ctx.strokeStyle = `rgba(180,190,255,${shockwaveAlpha * 0.3})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    // ── Phase 6: Brand reveal (24–28s) ──────────────────────
    if (elapsed > 24000) {
      const nameEl = document.getElementById('splash-name');
      const subEl  = document.getElementById('splash-sub');
      if (nameEl) nameEl.classList.add('visible');
      if (subEl && elapsed > 25500) subEl.classList.add('visible');
    }

    // ── Phase 7: Stabilization (28–30s) — handled by particle fade above

    // ── Auto-exit at 30s ─────────────────────────────────────
    if (elapsed >= SPLASH_DURATION) {
      exitSplash();
      return;
    }

    splashAnimId = requestAnimationFrame(draw);
  }

  splashAnimId = requestAnimationFrame(draw);
}

function initSplash() {
  splashDone = false;
  if (splashAnimId) { cancelAnimationFrame(splashAnimId); splashAnimId = null; }

  const splashScreen = document.getElementById('splash-screen');
  const mainApp      = document.getElementById('main-app');
  const el           = document.getElementById('splash');

  // ── STRICT SPLASH RULE ─────────────────────────────────────
  // Splash runs ONLY when the tab is freshly opened (no session key).
  // Everything else — form submits, fetch+reload, status changes,
  // link clicks, page navigation — sets the flag before leaving,
  // so splash is always skipped on return.
  //
  // sessionStorage is tab-scoped: it clears when the tab is closed
  // or when the user opens the app in a new tab. This is exactly
  // the "start" moment we want to show splash.
  //
  // We do NOT use isReload — reload within the same tab session
  // should also skip splash (user is working, not starting fresh).

  const splashShown = sessionStorage.getItem('aurix_splash_done');

  if (splashShown) {
    // Already shown this session — skip immediately
    if (splashScreen) splashScreen.style.display = 'none';
    if (mainApp)      mainApp.style.display = 'block';
    document.body.style.overflow = '';
    return;
  }

  // First time this tab session — show splash
  if (!splashScreen || !el) {
    if (mainApp) mainApp.style.display = 'block';
    return;
  }

  splashScreen.style.display = 'block';
  splashScreen.style.opacity = '1';
  if (mainApp) mainApp.style.display = 'none';
  el.classList.add('splash-active');
  document.body.style.overflow = 'hidden';
  cinematicSplash();
}

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
  sessionStorage.setItem('aurix_splash_done', '1');
  fetch('/toggle-task/' + id, {method:'POST'})
    .then(() => { sessionStorage.setItem('aurix_splash_done', '1'); location.reload(); });
}

// ─── CHAPTER QUICK STATUS ────────────────────────────
function quickUpdateChapter(sid, cid, status) {
  sessionStorage.setItem('aurix_splash_done', '1');
  const fd = new FormData(); fd.append('status', status);
  fetch(`/toggle-chapter/${sid}/${cid}`, {method:'POST', body:fd})
    .then(() => { sessionStorage.setItem('aurix_splash_done', '1'); location.reload(); });
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
  // Ctrl+S → replay splash animation
  if (e.ctrlKey && e.key === 's') {
    e.preventDefault();
    replaySplash();
    return;
  }
  if (e.altKey && !e.ctrlKey) {
    const map = {d:'/dashboard',h:'/habits',s:'/spending',
                 e:'/study',c:'/calendar',n:'/notes',g:'/goals',z:'/sleep',
                 i:'/insights',t:'/thoughts',r:'/remember'};
    if (map[e.key]) { e.preventDefault(); sessionStorage.setItem('aurix_splash_done', '1'); window.location.href = map[e.key]; }
  }
});

// ─── INIT ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSplash();
  animateBars();
  initBarTooltips();
  const today = new Date().toISOString().split('T')[0];
  document.querySelectorAll('input[type="date"]').forEach(el => { if (!el.value) el.value = today; });

  // ── Set splash-skip flag on EVERY navigation out of this page ──
  // Covers: link clicks, form submits, fetch+reload, JS navigation.
  // Splash only resets when user opens a new tab (sessionStorage clears).

  // 1. Anchor clicks
  document.addEventListener('click', (e) => {
    const anchor = e.target.closest('a[href]');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (href && href.startsWith('/') && !href.startsWith('//')) {
      sessionStorage.setItem('aurix_splash_done', '1');
    }
  }, true);

  // 2. Form submits — covers ALL status dropdowns, add/edit forms, link/unlink
  document.addEventListener('submit', () => {
    sessionStorage.setItem('aurix_splash_done', '1');
  }, true);

  // 3. beforeunload — catches any remaining navigation (JS redirects etc.)
  window.addEventListener('beforeunload', () => {
    sessionStorage.setItem('aurix_splash_done', '1');
  });
});

/* ══════════════════════════════════════════════════
   MILESTONE FUNCTIONS (fixed)
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
// ── Goal ↔ Exam Linking (Part D) ───────────────────────
// pending unlink target
let _unlinkTarget = {};

function linkExam(gid) {
  const sel = document.getElementById('link-select-' + gid);
  if (!sel || !sel.value) { showToast('Select an exam first', 'warn'); return; }
  const btn = document.getElementById('link-btn-' + gid);
  // Loading state
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
        setTimeout(() => { sessionStorage.setItem('aurix_splash_done','1'); location.reload(); }, 600);
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
      .then(() => { showToast('Exam unlinked', 'success'); sessionStorage.setItem('aurix_splash_done','1'); location.reload(); });
  }, 300);
}

// Legacy alias
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
        // Update button UI
        if (btnEl) {
          btnEl.textContent = '⏹ Stop';
          btnEl.className = 'btn-stop-study';
          btnEl.onclick = () => stopStudySession(chapterId, subjectId, btnEl);
        }
        // Start elapsed counter
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
        setTimeout(() => { sessionStorage.setItem('aurix_splash_done','1'); location.reload(); }, 800);
      } else {
        showToast(d.msg || 'No active session', 'warn');
      }
    });
}

// Poll active session on page load to restore timer if active
function checkActiveStudySession() {
  fetch('/active-session-status')
    .then(r => r.json())
    .then(d => {
      if (d.study) {
        const cid = d.study.chapter_id;
        const sid = d.study.subject_id;
        const elapsed = d.study.elapsed_seconds || 0;
        // Restore timer display
        const timerEl = document.getElementById(`study-timer-${cid}`);
        if (timerEl) {
          let secs = elapsed;
          studyTimerInterval = setInterval(() => {
            secs++;
            const m = Math.floor(secs / 60), s = secs % 60;
            timerEl.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
          }, 1000);
        }
        // Update button if present
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
        setTimeout(() => { sessionStorage.setItem('aurix_splash_done','1'); location.reload(); }, 800);
      } else {
        showToast(d.msg || 'No active sleep session', 'warn');
      }
    });
}

// ── Restore active session check on load ──────────
document.addEventListener('DOMContentLoaded', () => {
  checkActiveStudySession();
});
