/* ═══════════════════════════════════════════════════════════════
   AURIX Service Worker v3
   — Scope: / (root, controls all pages)
   — Registered from: /sw.js  (served by Flask with correct headers)
   ═══════════════════════════════════════════════════════════════ */

const CACHE_VER  = 'aurix-v3';
const CACHE_URLS = ['/static/style.css', '/static/script.js', '/static/favicon.svg'];

/* ── Install: cache static assets ─────────────────────────────── */
self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE_VER)
      .then(c => c.addAll(CACHE_URLS))
      .catch(() => {/* non-fatal */})
  );
  self.skipWaiting();
});

/* ── Activate: clean old caches ───────────────────────────────── */
self.addEventListener('activate', ev => {
  ev.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VER).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
  /* Register a periodic background sync if the browser supports it */
  self.registration.periodicSync?.register('aurix-reminder-poll', {
    minInterval: 60 * 1000  // 1 minute minimum
  }).catch(() => {});
});

/* ── Fetch: network-first for API, cache-first for statics ─────── */
self.addEventListener('fetch', ev => {
  const url = ev.request.url;
  if (ev.request.method !== 'GET') return;

  /* Never intercept API calls */
  if (url.includes('/api/')) return;

  if (url.includes('/static/')) {
    ev.respondWith(
      caches.match(ev.request).then(cached =>
        cached || fetch(ev.request).then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_VER).then(c => c.put(ev.request, clone));
          return resp;
        })
      )
    );
  }
});

/* ── Background periodic sync ─────────────────────────────────── */
self.addEventListener('periodicsync', ev => {
  if (ev.tag === 'aurix-reminder-poll') {
    ev.waitUntil(pollAndNotify());
  }
});

/* ── Manual background sync ───────────────────────────────────── */
self.addEventListener('sync', ev => {
  if (ev.tag === 'aurix-reminder-check') {
    ev.waitUntil(pollAndNotify());
  }
});

/* ── Push (server-initiated) ──────────────────────────────────── */
self.addEventListener('push', ev => {
  let payload = {
    title: 'AURIX Reminder',
    body:  'Time to check your habits',
    icon:  '/static/favicon.svg',
    url:   '/habits'
  };
  if (ev.data) {
    try { payload = { ...payload, ...ev.data.json() }; } catch {}
  }
  ev.waitUntil(showNotif(payload));
});

/* ── Message from page thread ─────────────────────────────────── */
self.addEventListener('message', ev => {
  const d = ev.data;
  if (!d) return;
  if (d.type === 'SHOW_NOTIFICATION') {
    showNotif({ title: d.title, body: d.body, url: d.url, tag: d.tag });
  }
  if (d.type === 'POLL_REMINDERS') {
    pollAndNotify();
  }
});

/* ── Notification click → open URL ───────────────────────────── */
self.addEventListener('notificationclick', ev => {
  ev.notification.close();
  const target = ev.notification.data?.url || '/';
  ev.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      /* Focus existing tab if one matches our origin */
      const existing = list.find(c => new URL(c.url).origin === self.location.origin);
      if (existing) {
        existing.navigate(target);
        return existing.focus();
      }
      return clients.openWindow(target);
    })
  );
});

/* ═══════════════════════════════════════════════════════════════
   CORE HELPERS
   ═══════════════════════════════════════════════════════════════ */

function showNotif(payload) {
  const { title = 'AURIX', body = '', url = '/', tag, icon } = payload;
  return self.registration.showNotification(title, {
    body,
    icon:              icon || '/static/favicon.svg',
    badge:             '/static/favicon.svg',
    tag:               tag || ('aurix-' + Date.now()),
    data:              { url },
    vibrate:           [200, 80, 200],
    requireInteraction: false,
    silent:            false
  });
}

async function pollAndNotify() {
  try {
    const resp = await fetch('/api/due-reminders', { cache: 'no-store' });
    if (!resp.ok) return;
    const { reminders = [] } = await resp.json();

    /* Only fire reminders not already shown this minute */
    const now  = new Date();
    const hhmm = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');

    for (const r of reminders) {
      const key = `sw_fired_${r.tag || r.id}_${now.toDateString()}_${hhmm}`;
      /* Use SW cache storage as dedup store (sessionStorage not available in SW) */
      const cache = await caches.open('aurix-sw-dedup');
      const hit   = await cache.match(key);
      if (hit) continue;
      await cache.put(key, new Response('1'));
      await showNotif({
        title: r.title,
        body:  r.body,
        url:   r.url,
        tag:   r.tag || r.id
      });
    }
  } catch(e) {
    console.warn('[AURIX SW] pollAndNotify error:', e);
  }
}
