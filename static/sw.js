/* ═══════════════════════════════════════════════════════════════════════
   AURIX Service Worker v4
   ─ Scope: / (root)
   ─ Registered from: /sw.js  (Flask serves with correct headers)
   ─ Fixed: iOS PWA support, proper error handling, mobile compatibility
   ═══════════════════════════════════════════════════════════════════════ */

const CACHE_VER  = 'aurix-v4';
const CACHE_URLS = ['/static/style.css', '/static/script.js', '/static/favicon.svg'];

/* ── Install: pre-cache static assets ─────────────────────────────────── */
self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE_VER)
      .then(c => c.addAll(CACHE_URLS))
      .catch(() => { /* non-fatal — offline caching optional */ })
  );
  self.skipWaiting();
});

/* ── Activate: clean stale caches, claim all clients ──────────────────── */
self.addEventListener('activate', ev => {
  ev.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_VER && k !== 'aurix-sw-dedup')
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

/* ── Fetch: network-first for API/HTML, cache-first for static assets ── */
self.addEventListener('fetch', ev => {
  if (ev.request.method !== 'GET') return;
  const url = ev.request.url;

  /* Never intercept API or HTML navigation */
  if (url.includes('/api/') || url.includes('/sw.js')) return;

  /* Static assets: cache-first with network fallback */
  if (url.includes('/static/')) {
    ev.respondWith(
      caches.match(ev.request).then(cached => {
        if (cached) return cached;
        return fetch(ev.request).then(resp => {
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE_VER).then(c => c.put(ev.request, clone));
          }
          return resp;
        }).catch(() => cached || new Response('', { status: 408 }));
      })
    );
    return;
  }

  /* Everything else: network-first (never block navigation) */
});

/* ── Background periodic sync (Chrome Android + desktop) ──────────────── */
self.addEventListener('periodicsync', ev => {
  if (ev.tag === 'aurix-reminder-poll') {
    ev.waitUntil(pollAndNotify());
  }
});

/* ── One-off background sync ───────────────────────────────────────────── */
self.addEventListener('sync', ev => {
  if (ev.tag === 'aurix-reminder-check') {
    ev.waitUntil(pollAndNotify());
  }
});

/* ── Push (server-initiated) ───────────────────────────────────────────── */
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

/* ── Message from page thread ──────────────────────────────────────────── */
self.addEventListener('message', ev => {
  const d = ev.data;
  if (!d) return;
  if (d.type === 'SHOW_NOTIFICATION') {
    showNotif({ title: d.title, body: d.body, url: d.url, tag: d.tag });
  }
  if (d.type === 'POLL_REMINDERS') {
    pollAndNotify();
  }
  /* Keepalive ping — page sends this to ensure SW stays active */
  if (d.type === 'PING') {
    ev.source?.postMessage({ type: 'PONG' });
  }
});

/* ── Notification click → focus or open the app ───────────────────────── */
self.addEventListener('notificationclick', ev => {
  ev.notification.close();
  const target = ev.notification.data?.url || '/';
  ev.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const match = list.find(c =>
        new URL(c.url).origin === self.location.origin
      );
      if (match) {
        return match.navigate(target).then(c => c.focus()).catch(() => match.focus());
      }
      return clients.openWindow(target);
    })
  );
});

/* ═══════════════════════════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════════════════════════ */

function showNotif(payload) {
  const { title = 'AURIX', body = '', url = '/', tag, icon } = payload;
  /* showNotification requires notification permission — guard it */
  if (Notification.permission !== 'granted') return Promise.resolve();
  return self.registration.showNotification(title, {
    body,
    icon:               icon || '/static/favicon.svg',
    badge:              '/static/favicon.svg',
    tag:                tag || ('aurix-' + Date.now()),
    data:               { url },
    vibrate:            [200, 80, 200],
    requireInteraction: false,
    silent:             false,
  }).catch(err => console.warn('[AURIX SW] showNotification error:', err));
}

async function pollAndNotify() {
  /* Safety: only run if permission is granted */
  if (Notification.permission !== 'granted') return;

  try {
    const resp = await fetch('/api/due-reminders', {
      cache: 'no-store',
      /* Include credentials so Flask session works */
      credentials: 'same-origin',
    });
    if (!resp.ok) return;

    const { reminders = [] } = await resp.json();
    if (!reminders.length) return;

    const now  = new Date();
    const hhmm = now.getHours().toString().padStart(2, '0') + ':' +
                 now.getMinutes().toString().padStart(2, '0');

    /* Use SW cache as dedup store (sessionStorage unavailable in SW) */
    const dedup = await caches.open('aurix-sw-dedup').catch(() => null);

    for (const r of reminders) {
      const key = `sw_fired_${r.tag || r.id}_${now.toDateString()}_${hhmm}`;
      if (dedup) {
        const hit = await dedup.match(key).catch(() => null);
        if (hit) continue;
        await dedup.put(key, new Response('1')).catch(() => {});
      }
      await showNotif({
        title: r.title,
        body:  r.body,
        url:   r.url,
        tag:   r.tag || r.id,
      });
    }

    /* Prune dedup cache entries older than 2 days to prevent unbounded growth */
    if (dedup) {
      const keys = await dedup.keys().catch(() => []);
      const cutoff = new Date(Date.now() - 48 * 60 * 60 * 1000).toDateString();
      for (const req of keys) {
        if (req.url.includes(cutoff)) continue;  // keep today/yesterday
        /* Simple heuristic: if key doesn't contain today or yesterday, delete */
        const today     = new Date().toDateString();
        const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toDateString();
        if (!req.url.includes(today) && !req.url.includes(yesterday)) {
          dedup.delete(req).catch(() => {});
        }
      }
    }
  } catch (e) {
    /* Silently swallow network errors — SW must never crash */
    console.warn('[AURIX SW] pollAndNotify error:', e.message || e);
  }
}
