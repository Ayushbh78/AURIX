/* ══════════════════════════════════════════════════════════════════
   AURIX — Notification & Reminder System  v2.0
   Handles: PWA push, local scheduling, notification center,
            weekly/monthly insights, sound, SW registration
   ══════════════════════════════════════════════════════════════════ */

'use strict';

// ──────────────────────────────────────────────────────────────────
// CONSTANTS
// ──────────────────────────────────────────────────────────────────
const AURIX_NS  = 'aurix_notifications';   // localStorage key — notification history
const AURIX_REM = 'aurix_reminders';       // localStorage key — reminder configs
const AURIX_INS = 'aurix_insights_sent';   // localStorage key — insight report tracking

const NOTIF_SOUNDS = {
  default: null,   // browser default
  chime:   '/static/sounds/chime.mp3',
  bell:    '/static/sounds/bell.mp3',
  alert:   '/static/sounds/alert.mp3'
};

let _swReg        = null;   // ServiceWorkerRegistration
let _checkInterval= null;   // setInterval handle
let _audioCtx     = null;   // AudioContext for synthetic tones

// ──────────────────────────────────────────────────────────────────
// 1. SERVICE WORKER REGISTRATION
// ──────────────────────────────────────────────────────────────────
async function initServiceWorker() {
  if (!('serviceWorker' in navigator)) return null;
  try {
    _swReg = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;

    // Push scheduled reminders into SW so background alarms work
    syncRemindersToSW();

    // Listen for navigation messages from SW (notification click)
    navigator.serviceWorker.addEventListener('message', event => {
      if (event.data?.type === 'NAVIGATE') {
        window.location.href = event.data.url;
      }
    });

    return _swReg;
  } catch (e) {
    console.warn('AURIX SW registration failed:', e);
    return null;
  }
}

// ──────────────────────────────────────────────────────────────────
// 2. PERMISSION HANDLING
// ──────────────────────────────────────────────────────────────────
async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    showToast('Notifications not supported in this browser', 'warn');
    return 'denied';
  }
  if (Notification.permission === 'granted') return 'granted';

  const result = await Notification.requestPermission();
  if (result === 'granted') {
    showToast('🔔 Notifications enabled!', 'success');
    addInAppNotification({
      title:   '🔔 Notifications Enabled',
      body:    'You will now receive habit reminders and insights.',
      type:    'system',
      link:    '/habits'
    });
    startReminderLoop();
  } else {
    showToast('Notifications blocked — reminders will show inside the app only', 'warn');
  }
  return result;
}

function canPushNotify() {
  return 'Notification' in window && Notification.permission === 'granted';
}

// ──────────────────────────────────────────────────────────────────
// 3. FIRE A NOTIFICATION (push or in-app fallback)
// ──────────────────────────────────────────────────────────────────
async function fireNotification({ title, body, link = '/habits', tag, sound = 'default', icon }) {
  // Always add to in-app notification center
  addInAppNotification({ title, body, type: 'reminder', link });

  if (!canPushNotify()) return;

  playNotificationSound(sound);

  const opts = {
    body,
    icon:    icon || '/static/favicon.svg',
    badge:   '/static/favicon.svg',
    tag:     tag || `aurix-${Date.now()}`,
    data:    { link, sound },
    vibrate: [200, 100, 200, 100, 400],
    requireInteraction: false,
    silent:  false,
    actions: [
      { action: 'open',    title: '✅ Open' },
      { action: 'dismiss', title: '✕ Dismiss' }
    ]
  };

  try {
    if (_swReg) {
      await _swReg.showNotification(title, opts);
    } else {
      new Notification(title, opts);
    }
  } catch (e) {
    console.warn('Notification error:', e);
  }
}

// ──────────────────────────────────────────────────────────────────
// 4. SOUND ENGINE (synthetic tones — no file dependency)
// ──────────────────────────────────────────────────────────────────
function playNotificationSound(soundKey) {
  try {
    if (!_audioCtx) {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (_audioCtx.state === 'suspended') _audioCtx.resume();

    const filePath = NOTIF_SOUNDS[soundKey] || null;
    if (filePath) {
      // Try loading the file first
      fetch(filePath).then(r => {
        if (r.ok) {
          r.arrayBuffer().then(buf => {
            _audioCtx.decodeAudioData(buf).then(decoded => {
              const src = _audioCtx.createBufferSource();
              src.buffer = decoded;
              src.connect(_audioCtx.destination);
              src.start();
            }).catch(() => playTone());
          });
        } else {
          playTone();
        }
      }).catch(() => playTone());
    } else {
      playTone();
    }
  } catch (e) {
    // Audio not available — silent notification
  }
}

function playTone(freq = 880, duration = 0.3, type = 'sine') {
  try {
    if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc   = _audioCtx.createOscillator();
    const gain  = _audioCtx.createGain();
    osc.connect(gain);
    gain.connect(_audioCtx.destination);
    osc.type      = type;
    osc.frequency.setValueAtTime(freq, _audioCtx.currentTime);
    gain.gain.setValueAtTime(0.3, _audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, _audioCtx.currentTime + duration);
    osc.start();
    osc.stop(_audioCtx.currentTime + duration);
  } catch (e) {}
}

// ──────────────────────────────────────────────────────────────────
// 5. REMINDER STORAGE (localStorage — persists across sessions)
// ──────────────────────────────────────────────────────────────────
function loadReminders() {
  try {
    return JSON.parse(localStorage.getItem(AURIX_REM) || '{}');
  } catch { return {}; }
}

function saveReminders(obj) {
  localStorage.setItem(AURIX_REM, JSON.stringify(obj));
}

/**
 * Set reminder times for a habit.
 * @param {number} habitId
 * @param {string[]} times  — array of "HH:MM" strings
 * @param {boolean} enabled
 * @param {string}  sound
 * @param {string}  message — custom notification body
 */
function setHabitReminder(habitId, times, enabled = true, sound = 'default', message = '') {
  const all = loadReminders();
  all[habitId] = { times, enabled, sound, message, updatedAt: new Date().toISOString() };
  saveReminders(all);
  syncRemindersToSW();
}

function removeHabitReminder(habitId) {
  const all = loadReminders();
  delete all[habitId];
  saveReminders(all);
  syncRemindersToSW();
}

function getHabitReminder(habitId) {
  return loadReminders()[habitId] || null;
}

// Push all reminder configs into Service Worker so it can alarm in background
function syncRemindersToSW() {
  if (!navigator.serviceWorker?.controller) return;
  const reminders = loadReminders();
  // We need habit names — load from window.AURIX_HABITS if available
  const habits = window.AURIX_HABITS || [];
  const payload = Object.entries(reminders)
    .filter(([, r]) => r.enabled)
    .map(([id, r]) => {
      const habit = habits.find(h => String(h.id) === String(id));
      return {
        id,
        name:    habit?.name || `Habit #${id}`,
        times:   r.times,
        sound:   r.sound,
        message: r.message || `Time to complete: ${habit?.name || 'your habit'}!`
      };
    });

  navigator.serviceWorker.controller.postMessage({
    type: 'SCHEDULE_REMINDERS',
    reminders: payload
  });
}

// ──────────────────────────────────────────────────────────────────
// 6. REMINDER SCHEDULER LOOP (runs every minute in-tab)
// ──────────────────────────────────────────────────────────────────
// Tracks which (habitId + HH:MM + date) combos already fired today
const _firedToday = new Set();

function startReminderLoop() {
  if (_checkInterval) clearInterval(_checkInterval);

  const check = () => {
    const now     = new Date();
    const todayKey = now.toISOString().slice(0, 10);          // YYYY-MM-DD
    const hhmm    = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const reminders = loadReminders();

    // Reset fired set at midnight
    if (_firedToday._date !== todayKey) {
      _firedToday.clear();
      _firedToday._date = todayKey;
    }

    const habits = window.AURIX_HABITS || [];

    for (const [id, rem] of Object.entries(reminders)) {
      if (!rem.enabled) continue;
      for (const t of (rem.times || [])) {
        const fireKey = `${id}-${t}-${todayKey}`;
        if (_firedToday.has(fireKey)) continue;
        if (t === hhmm) {
          _firedToday.add(fireKey);
          const habit = habits.find(h => String(h.id) === String(id));
          const hName = habit?.name || `Habit #${id}`;
          const isDone = (window.AURIX_DONE_TODAY || []).includes(Number(id));

          if (!isDone) {
            fireNotification({
              title: `⏰ Habit Reminder`,
              body:  rem.message || `Time to complete: ${hName}!`,
              link:  '/habits',
              tag:   `habit-${id}-${hhmm}`,
              sound: rem.sound || 'default'
            });
          }
        }
      }
    }

    // Check for weekly/monthly insights
    checkInsightNotifications(now, todayKey);
  };

  check(); // run immediately
  _checkInterval = setInterval(check, 60_000);
}

// ──────────────────────────────────────────────────────────────────
// 7. WEEKLY / MONTHLY INSIGHT NOTIFICATIONS
// ──────────────────────────────────────────────────────────────────
function checkInsightNotifications(now, todayKey) {
  const sent = getInsightsSent();

  // Weekly — every Sunday at 20:00
  if (now.getDay() === 0 && now.getHours() === 20 && now.getMinutes() === 0) {
    const weekKey = `weekly-${todayKey}`;
    if (!sent[weekKey]) {
      sent[weekKey] = true;
      saveInsightsSent(sent);
      fireNotification({
        title: '📊 Your Weekly Report is Ready',
        body:  'See your habit completion rate, streaks, and productivity trends.',
        link:  '/insights',
        tag:   weekKey,
        sound: 'chime'
      });
    }
  }

  // Monthly — 1st of month at 09:00
  if (now.getDate() === 1 && now.getHours() === 9 && now.getMinutes() === 0) {
    const monthKey = `monthly-${now.getFullYear()}-${now.getMonth()}`;
    if (!sent[monthKey]) {
      sent[monthKey] = true;
      saveInsightsSent(sent);
      fireNotification({
        title: '📅 Monthly Report Ready',
        body:  'Your monthly productivity summary is now available.',
        link:  '/insights',
        tag:   monthKey,
        sound: 'bell'
      });
    }
  }

  // Daily morning reminder at 08:00 — habits not set yet
  if (now.getHours() === 8 && now.getMinutes() === 0) {
    const dailyKey = `daily-morning-${todayKey}`;
    if (!sent[dailyKey]) {
      sent[dailyKey] = true;
      saveInsightsSent(sent);
      const done  = (window.AURIX_DONE_TODAY || []).length;
      const total = (window.AURIX_HABITS || []).length;
      if (total > 0 && done < total) {
        fireNotification({
          title: '🌅 Good Morning!',
          body:  `You have ${total - done} habit${total - done > 1 ? 's' : ''} to complete today.`,
          link:  '/habits',
          tag:   dailyKey
        });
      }
    }
  }

  // Evening reminder at 21:00 — missed habits
  if (now.getHours() === 21 && now.getMinutes() === 0) {
    const eveningKey = `daily-evening-${todayKey}`;
    if (!sent[eveningKey]) {
      const done  = (window.AURIX_DONE_TODAY || []).length;
      const total = (window.AURIX_HABITS || []).length;
      if (total > 0 && done < total) {
        sent[eveningKey] = true;
        saveInsightsSent(sent);
        fireNotification({
          title: '⚠️ Habit Pending',
          body:  `${total - done} habit${total - done > 1 ? 's' : ''} still incomplete today. Don't break your streak!`,
          link:  '/habits',
          tag:   eveningKey,
          sound: 'alert'
        });
      }
    }
  }
}

function getInsightsSent() {
  try { return JSON.parse(localStorage.getItem(AURIX_INS) || '{}'); } catch { return {}; }
}
function saveInsightsSent(obj) {
  localStorage.setItem(AURIX_INS, JSON.stringify(obj));
}

// ──────────────────────────────────────────────────────────────────
// 8. IN-APP NOTIFICATION CENTER
// ──────────────────────────────────────────────────────────────────
function loadNotifications() {
  try {
    return JSON.parse(localStorage.getItem(AURIX_NS) || '[]');
  } catch { return []; }
}

function saveNotifications(arr) {
  // Keep last 200
  localStorage.setItem(AURIX_NS, JSON.stringify(arr.slice(-200)));
}

function addInAppNotification({ title, body, type = 'info', link = '/', icon }) {
  const notifications = loadNotifications();
  const notif = {
    id:       Date.now(),
    title,
    body,
    type,      // 'reminder' | 'insight' | 'system' | 'info'
    link,
    icon:      icon || typeIcon(type),
    read:      false,
    timestamp: new Date().toISOString()
  };
  notifications.unshift(notif);
  saveNotifications(notifications);

  // Update badge count in UI
  updateNotificationBadge();

  return notif;
}

function markAllRead() {
  const notifications = loadNotifications();
  notifications.forEach(n => n.read = true);
  saveNotifications(notifications);
  updateNotificationBadge();
}

function markRead(id) {
  const notifications = loadNotifications();
  const n = notifications.find(n => n.id === id);
  if (n) { n.read = true; saveNotifications(notifications); }
  updateNotificationBadge();
}

function clearAllNotifications() {
  saveNotifications([]);
  updateNotificationBadge();
}

function unreadCount() {
  return loadNotifications().filter(n => !n.read).length;
}

function updateNotificationBadge() {
  const count = unreadCount();
  const badge = document.getElementById('notif-badge');
  if (badge) {
    badge.textContent = count > 99 ? '99+' : count;
    badge.style.display = count > 0 ? 'flex' : 'none';
  }
  // Update page title badge
  if (count > 0 && !document.title.startsWith('(')) {
    document.title = `(${count}) ${document.title.replace(/^\(\d+\)\s*/, '')}`;
  } else if (count === 0) {
    document.title = document.title.replace(/^\(\d+\)\s*/, '');
  }
}

function typeIcon(type) {
  const icons = {
    reminder: '⏰',
    insight:  '📊',
    system:   '🔔',
    info:     'ℹ️',
    success:  '✅',
    warning:  '⚠️'
  };
  return icons[type] || '🔔';
}

// ──────────────────────────────────────────────────────────────────
// 9. NOTIFICATION PANEL UI
// ──────────────────────────────────────────────────────────────────
function renderNotificationPanel() {
  const panel = document.getElementById('aurix-notif-panel');
  if (!panel) return;

  const notifications = loadNotifications();
  const hasUnread = notifications.some(n => !n.read);

  if (notifications.length === 0) {
    panel.innerHTML = `
      <div class="notif-panel-header">
        <div class="notif-panel-title">🔔 Notifications</div>
        <button class="notif-panel-close" onclick="closeNotifPanel()">✕</button>
      </div>
      <div class="notif-empty">
        <div style="font-size:2.5rem;margin-bottom:8px">🔔</div>
        <div style="font-size:14px;font-weight:600;color:var(--text2)">No notifications yet</div>
        <div style="font-size:12px;color:var(--text3);margin-top:4px">Habit reminders and insights will appear here</div>
      </div>`;
    return;
  }

  const grouped = groupByDate(notifications);

  panel.innerHTML = `
    <div class="notif-panel-header">
      <div class="notif-panel-title">🔔 Notifications
        ${unreadCount() > 0 ? `<span class="notif-count-chip">${unreadCount()}</span>` : ''}
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        ${hasUnread ? `<button class="notif-action-btn" onclick="markAllRead();renderNotificationPanel()">Mark all read</button>` : ''}
        <button class="notif-action-btn notif-clear-btn" onclick="if(confirm('Clear all?')){clearAllNotifications();renderNotificationPanel()}">Clear all</button>
        <button class="notif-panel-close" onclick="closeNotifPanel()">✕</button>
      </div>
    </div>
    <div class="notif-panel-body">
      ${Object.entries(grouped).map(([date, items]) => `
        <div class="notif-date-label">${date}</div>
        ${items.map(n => `
          <div class="notif-item ${n.read ? '' : 'notif-unread'}" onclick="markRead(${n.id});renderNotificationPanel();window.location.href='${n.link}'">
            <div class="notif-icon">${n.icon || typeIcon(n.type)}</div>
            <div class="notif-content">
              <div class="notif-title">${escapeHtml(n.title)}</div>
              <div class="notif-body">${escapeHtml(n.body)}</div>
              <div class="notif-time">${formatRelativeTime(n.timestamp)}</div>
            </div>
            ${!n.read ? '<div class="notif-dot"></div>' : ''}
          </div>
        `).join('')}
      `).join('')}
    </div>`;
}

function groupByDate(notifications) {
  const groups = {};
  const today  = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  for (const n of notifications) {
    const d = new Date(n.timestamp).toDateString();
    const label = d === today ? 'Today' : d === yesterday ? 'Yesterday' : new Date(n.timestamp).toLocaleDateString('en-US', {month:'short',day:'numeric'});
    if (!groups[label]) groups[label] = [];
    groups[label].push(n);
  }
  return groups;
}

function formatRelativeTime(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60000)  return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff/3600000)}h ago`;
  return new Date(iso).toLocaleDateString('en-US', {month:'short',day:'numeric'});
}

function escapeHtml(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let _notifPanelOpen = false;

function openNotifPanel() {
  _notifPanelOpen = true;
  const panel = document.getElementById('aurix-notif-panel');
  const overlay = document.getElementById('aurix-notif-overlay');
  if (panel)   { panel.classList.add('notif-panel-open');    renderNotificationPanel(); }
  if (overlay) overlay.classList.add('notif-overlay-show');
}

function closeNotifPanel() {
  _notifPanelOpen = false;
  const panel = document.getElementById('aurix-notif-panel');
  const overlay = document.getElementById('aurix-notif-overlay');
  if (panel)   panel.classList.remove('notif-panel-open');
  if (overlay) overlay.classList.remove('notif-overlay-show');
}

function toggleNotifPanel() {
  _notifPanelOpen ? closeNotifPanel() : openNotifPanel();
}

// ──────────────────────────────────────────────────────────────────
// 10. REMINDER MODAL (habit reminder setup)
// ──────────────────────────────────────────────────────────────────
function openReminderModal(habitId, habitName) {
  const existing = getHabitReminder(habitId) || { times: [], enabled: true, sound: 'default', message: '' };

  const timesHtml = existing.times.length
    ? existing.times.map((t, i) => reminderTimeRow(t, i)).join('')
    : reminderTimeRow('08:00', 0);

  const modalHtml = `
    <div class="modal-header">
      <h3>⏰ Set Reminder — ${escapeHtml(habitName)}</h3>
    </div>
    <div id="reminder-times-list">
      ${timesHtml}
    </div>
    <button class="btn-secondary btn-sm" style="margin-top:8px;width:100%" onclick="addReminderTimeRow()">+ Add Another Time</button>

    <div class="form-group" style="margin-top:16px">
      <label>Custom Message (optional)</label>
      <input type="text" id="rem-message" class="form-input" value="${escapeHtml(existing.message)}"
             placeholder="e.g. Time to Study!, Don't skip today!"/>
    </div>

    <div class="form-group">
      <label>Notification Sound</label>
      <select id="rem-sound" class="form-input">
        <option value="default" ${existing.sound==='default'?'selected':''}>🔔 Default Tone</option>
        <option value="chime"   ${existing.sound==='chime'?'selected':''}>🎵 Chime</option>
        <option value="bell"    ${existing.sound==='bell'?'selected':''}>🔔 Bell</option>
        <option value="alert"   ${existing.sound==='alert'?'selected':''}>🚨 Alert</option>
      </select>
    </div>

    <div class="form-group">
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
        <input type="checkbox" id="rem-enabled" ${existing.enabled?'checked':''} style="width:18px;height:18px;accent-color:var(--indigo)"/>
        <span>Reminder Enabled (repeats daily)</span>
      </label>
    </div>

    <div class="form-actions">
      <button class="btn-secondary" onclick="closeActiveModal()">Cancel</button>
      <button class="btn-primary" onclick="saveReminderModal(${habitId})">💾 Save Reminder</button>
    </div>`;

  // Inject into modal system
  let modal = document.getElementById('reminder-modal-content');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'reminder-modal-content';
    modal.className = 'modal-content';
    document.getElementById('active-modal')?.appendChild(modal);
  }
  modal.innerHTML = modalHtml;
  modal.classList.remove('hidden');
  openModal('reminder-modal-content');
}

function reminderTimeRow(time, idx) {
  return `
    <div class="reminder-time-row" id="rem-row-${idx}" data-idx="${idx}">
      <input type="time" class="form-input rem-time-input" value="${time}" style="flex:1"/>
      <button class="icon-btn icon-btn-danger" onclick="removeReminderTimeRow(${idx})" title="Remove">✕</button>
    </div>`;
}

let _remRowIdx = 0;
function addReminderTimeRow() {
  _remRowIdx++;
  const list = document.getElementById('reminder-times-list');
  if (list) {
    const div = document.createElement('div');
    div.innerHTML = reminderTimeRow('09:00', _remRowIdx);
    list.appendChild(div.firstElementChild);
  }
}

function removeReminderTimeRow(idx) {
  const row = document.getElementById(`rem-row-${idx}`);
  if (row) row.remove();
}

async function saveReminderModal(habitId) {
  const times   = [...document.querySelectorAll('.rem-time-input')].map(i => i.value).filter(Boolean);
  const sound   = document.getElementById('rem-sound')?.value || 'default';
  const message = document.getElementById('rem-message')?.value?.trim() || '';
  const enabled = document.getElementById('rem-enabled')?.checked !== false;

  if (times.length === 0) {
    showToast('Add at least one reminder time', 'warn');
    return;
  }

  // Ensure permission
  if (canPushNotify() === false && Notification.permission !== 'granted') {
    const perm = await requestNotificationPermission();
    if (perm !== 'granted') {
      showToast('Reminders saved but push notifications blocked — will show in-app only', 'warn');
    }
  }

  setHabitReminder(habitId, times, enabled, sound, message);
  closeActiveModal();
  showToast(`✅ Reminder set for ${times.join(', ')} daily`, 'success');

  // Show confirmation notification
  addInAppNotification({
    title: '⏰ Reminder Set',
    body:  `Reminder at ${times.join(', ')} saved successfully.`,
    type:  'system',
    link:  '/habits'
  });

  // Update badge
  updateNotificationBadge();
  updateReminderBadges();
}

// Show indicator on habit cards that have reminders
function updateReminderBadges() {
  const reminders = loadReminders();
  document.querySelectorAll('[data-hid]').forEach(el => {
    const hid = el.dataset.hid;
    const rem = reminders[hid];
    const badge = el.querySelector('.reminder-badge') || createReminderBadge(el, hid);
    if (badge) {
      badge.style.display = (rem?.enabled && rem?.times?.length) ? 'inline-flex' : 'none';
      badge.title = rem?.times?.join(', ') || '';
    }
  });
}

function createReminderBadge(parent, hid) {
  // Inject small clock icon badge if container is a habit card
  if (!parent.classList.contains('habit-card')) return null;
  const badge = document.createElement('span');
  badge.className  = 'reminder-badge';
  badge.innerHTML  = '⏰';
  badge.style.cssText = 'display:none;position:absolute;top:8px;right:36px;font-size:14px;cursor:pointer;';
  badge.onclick = e => { e.stopPropagation(); openReminderModal(hid, ''); };
  parent.style.position = 'relative';
  parent.appendChild(badge);
  return badge;
}

// ──────────────────────────────────────────────────────────────────
// 11. WEEKLY / MONTHLY INSIGHT GENERATION (client-side)
// ──────────────────────────────────────────────────────────────────
async function generateWeeklyInsight() {
  try {
    const res = await fetch('/api/insights-data');
    const data = await res.json();
    const { habit_completion_pct, streak, completed_habits, missed_habits, total_habits } = data;

    const msg = completed_habits >= total_habits
      ? `🏆 Perfect week! You completed all ${total_habits} habits.`
      : `You completed ${completed_habits}/${total_habits} habits (${habit_completion_pct}%). Keep it up!`;

    addInAppNotification({
      title: '📊 Weekly Habit Report',
      body:  msg,
      type:  'insight',
      link:  '/insights'
    });

    if (canPushNotify()) {
      await fireNotification({
        title: '📊 Your Weekly Report is Ready',
        body:  msg,
        link:  '/insights',
        tag:   `weekly-insight-${Date.now()}`,
        sound: 'chime'
      });
    }
  } catch (e) {
    console.warn('Insight generation failed:', e);
  }
}

async function generateMonthlyInsight() {
  try {
    const res = await fetch('/api/insights-data');
    const data = await res.json();
    const { habit_completion_pct, best_streak } = data;

    addInAppNotification({
      title: '📅 Monthly Summary',
      body:  `${habit_completion_pct}% habit completion this month. Best streak: ${best_streak} days.`,
      type:  'insight',
      link:  '/insights'
    });
  } catch (e) {}
}

// ──────────────────────────────────────────────────────────────────
// 12. INIT — runs on every page load
// ──────────────────────────────────────────────────────────────────
async function initAURIXNotifications() {
  await initServiceWorker();

  // Update badge on load
  updateNotificationBadge();
  updateReminderBadges();

  // Start reminder loop if permission already granted
  if (canPushNotify()) {
    startReminderLoop();
  } else if (Notification.permission === 'default') {
    // Show subtle prompt after 3s on habits page
    if (window.location.pathname.includes('habit')) {
      setTimeout(() => {
        if (!localStorage.getItem('aurix_notif_asked')) {
          localStorage.setItem('aurix_notif_asked', '1');
          showNotifPromptBanner();
        }
      }, 3000);
    }
  }

  // Register periodic background sync (where supported)
  if (_swReg && 'periodicSync' in _swReg) {
    try {
      await _swReg.periodicSync.register('aurix-habit-reminders', { minInterval: 60 * 1000 });
    } catch (e) {}
  }
}

function showNotifPromptBanner() {
  const banner = document.createElement('div');
  banner.id = 'notif-prompt-banner';
  banner.className = 'notif-prompt-banner';
  banner.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;flex:1">
      <span style="font-size:1.5rem">🔔</span>
      <div>
        <div style="font-weight:700;font-size:14px">Enable Habit Reminders</div>
        <div style="font-size:12px;color:var(--text3)">Get notified at your set times even when the app is closed</div>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-shrink:0">
      <button class="btn-primary btn-sm" onclick="requestNotificationPermission().then(()=>startReminderLoop());document.getElementById('notif-prompt-banner').remove()">Enable</button>
      <button class="btn-secondary btn-sm" onclick="document.getElementById('notif-prompt-banner').remove()">Later</button>
    </div>`;
  document.querySelector('.page-content')?.prepend(banner);
}

// ──────────────────────────────────────────────────────────────────
// EXPORTS — attach to window so templates can call these
// ──────────────────────────────────────────────────────────────────
Object.assign(window, {
  // Notification permission & firing
  requestNotificationPermission,
  fireNotification,
  // Reminder management
  openReminderModal,
  setHabitReminder,
  removeHabitReminder,
  getHabitReminder,
  saveReminderModal,
  addReminderTimeRow,
  removeReminderTimeRow,
  // Notification center
  openNotifPanel,
  closeNotifPanel,
  toggleNotifPanel,
  renderNotificationPanel,
  addInAppNotification,
  markAllRead,
  markRead,
  clearAllNotifications,
  unreadCount,
  updateNotificationBadge,
  updateReminderBadges,
  // Insights
  generateWeeklyInsight,
  generateMonthlyInsight,
});

// Auto-init
document.addEventListener('DOMContentLoaded', initAURIXNotifications);
