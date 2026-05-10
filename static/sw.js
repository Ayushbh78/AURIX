/* ══════════════════════════════════════════════════════════════════
   AURIX Service Worker — PWA Notifications & Background Sync
   Version 2.0 — Production Ready
   ══════════════════════════════════════════════════════════════════ */

const CACHE_NAME = 'aurix-v2';
const STATIC_ASSETS = [
  '/',
  '/static/style.css',
  '/static/script.js',
  '/static/favicon.ico',
  '/static/favicon.svg',
  '/static/notification-sound.mp3'
];

// ── Install ─────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
});

// ── Activate ────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch — Network first, cache fallback ───────────────────────────
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/static/sw.js')) return;

  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// ── Notification Click ───────────────────────────────────────────────
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const data = event.notification.data || {};
  const url  = data.link || '/habits';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.focus();
          client.postMessage({ type: 'NAVIGATE', url });
          return;
        }
      }
      return self.clients.openWindow(url);
    })
  );
});

// ── Push Events (server-triggered) ──────────────────────────────────
self.addEventListener('push', event => {
  let payload = { title: 'AURIX', body: 'You have a reminder', link: '/habits' };
  try { payload = event.data.json(); } catch (e) {}

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body:    payload.body,
      icon:    '/static/favicon.svg',
      badge:   '/static/favicon.svg',
      tag:     payload.tag || 'aurix-push',
      data:    payload,
      vibrate: [200, 100, 200],
      requireInteraction: true,
      actions: [
        { action: 'open',    title: '✅ Open App' },
        { action: 'dismiss', title: '✕ Dismiss'  }
      ]
    })
  );
});

// ── Message from Main Thread ─────────────────────────────────────────
self.addEventListener('message', event => {
  const msg = event.data;
  if (!msg || !msg.type) return;

  if (msg.type === 'SCHEDULE_REMINDERS') {
    // Store reminders in indexedDB for background checking
    scheduleReminderAlarms(msg.reminders);
  }

  if (msg.type === 'SHOW_NOTIFICATION') {
    showLocalNotification(msg.payload);
  }

  if (msg.type === 'PING') {
    event.ports[0] && event.ports[0].postMessage({ type: 'PONG' });
  }
});

// ── Background Sync ──────────────────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'check-reminders') {
    event.waitUntil(checkAndFireReminders());
  }
});

// ── Periodic Background Sync (where supported) ──────────────────────
self.addEventListener('periodicsync', event => {
  if (event.tag === 'aurix-habit-reminders') {
    event.waitUntil(checkAndFireReminders());
  }
});

// ══════════════════════════════════════════════════════════════════
// Internal Helpers
// ══════════════════════════════════════════════════════════════════

async function showLocalNotification({ title, body, link, tag, sound }) {
  return self.registration.showNotification(title || 'AURIX Reminder', {
    body:    body  || 'Time to complete your activity',
    icon:    '/static/favicon.svg',
    badge:   '/static/favicon.svg',
    tag:     tag   || 'aurix-reminder',
    data:    { link: link || '/habits', sound },
    vibrate: [300, 100, 300, 100, 300],
    requireInteraction: true,
    silent:  false,
    actions: [
      { action: 'open',    title: '✅ Mark Done' },
      { action: 'snooze',  title: '⏰ Snooze 10m' },
      { action: 'dismiss', title: '✕ Dismiss'    }
    ]
  });
}

// Store scheduled reminders in memory (cleared on SW restart)
let _scheduledReminders = [];

function scheduleReminderAlarms(reminders) {
  _scheduledReminders = reminders || [];
}

async function checkAndFireReminders() {
  const now  = new Date();
  const hhmm = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  for (const rem of _scheduledReminders) {
    if (!rem.times) continue;
    for (const t of rem.times) {
      if (t === hhmm) {
        await showLocalNotification({
          title: `⏰ ${rem.name}`,
          body:  rem.message || 'Time to complete your habit!',
          link:  '/habits',
          tag:   `habit-${rem.id}-${hhmm}`
        });
      }
    }
  }
}

// ── Alarm Loop — fires every minute to check scheduled reminders ────
setInterval(checkAndFireReminders, 60_000);
