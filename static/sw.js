/* ═══════════════════════════════════════════════════════════
   AURIX Service Worker — PWA Notifications & Caching
   ═══════════════════════════════════════════════════════════ */

const CACHE_NAME = 'aurix-v2';
const STATIC_ASSETS = ['/static/style.css', '/static/script.js', '/static/favicon.svg'];

// ── Install ──────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch (network-first, cache fallback for static) ─────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        return resp;
      }))
    );
  }
});

// ── Push notification handler ─────────────────────────────────
self.addEventListener('push', e => {
  let data = { title: 'AURIX', body: 'You have a new reminder', icon: '/static/favicon.svg', url: '/' };
  if (e.data) {
    try { data = { ...data, ...e.data.json() }; } catch {}
  }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || '/static/favicon.svg',
      badge: '/static/favicon.svg',
      tag: data.tag || 'aurix-notif-' + Date.now(),
      data: { url: data.url || '/' },
      vibrate: [200, 100, 200],
      requireInteraction: false
    })
  );
});

// ── Notification click ───────────────────────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});

// ── Background sync (reminder check) ─────────────────────────
self.addEventListener('sync', e => {
  if (e.tag === 'aurix-reminder-check') {
    e.waitUntil(checkReminders());
  }
});

async function checkReminders() {
  try {
    const resp = await fetch('/api/due-reminders');
    if (!resp.ok) return;
    const { reminders } = await resp.json();
    for (const r of (reminders || [])) {
      await self.registration.showNotification(r.title, {
        body: r.body,
        icon: '/static/favicon.svg',
        badge: '/static/favicon.svg',
        tag: r.id,
        data: { url: r.url || '/' },
        vibrate: [150, 75, 150]
      });
    }
  } catch {}
}

// ── Message from main thread ──────────────────────────────────
self.addEventListener('message', e => {
  if (e.data?.type === 'SHOW_NOTIFICATION') {
    const { title, body, url, tag } = e.data;
    self.registration.showNotification(title || 'AURIX', {
      body: body || '',
      icon: '/static/favicon.svg',
      badge: '/static/favicon.svg',
      tag: tag || 'aurix-' + Date.now(),
      data: { url: url || '/' },
      vibrate: [200, 100, 200]
    });
  }
});
