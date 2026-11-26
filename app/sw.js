/* Service worker: works offline, opens the right tender from a notification,
   and (on Android/Chrome) checks for new tenders in the background when allowed. */
const VERSION = 'tr-v2.3.0';
const SHELL = ['./', './index.html', './guide.html', './style.css', './app.js', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/badge-96.png', './icons/favicon-64.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k.startsWith('tr-v') && k !== VERSION).map((k) => caches.delete(k))
  )).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.includes('/data/')) {            // data: network first, cached copy when offline
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(VERSION).then((c) => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req)));
    return;
  }
  if (url.hostname.includes('fonts.g')) {            // fonts: cache first
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(VERSION).then((c) => c.put(req, copy));
      return res;
    })));
    return;
  }
  if (url.origin === location.origin) {               // app shell: cache first, refresh in background
    e.respondWith(caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => hit);
      return hit || net;
    }));
  }
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const target = new URL(e.notification.data && e.notification.data.url || './', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) {
      if (c.url.startsWith(self.registration.scope)) { c.navigate(target); return c.focus(); }
    }
    return self.clients.openWindow(target);
  }));
});

async function backgroundCheck() {
  const meta = await caches.open('tr-meta');
  const knownRes = await meta.match('known.json');
  const prefsRes = await meta.match('prefs.json');
  const known = knownRes ? await knownRes.json() : [];
  const prefs = prefsRes ? await prefsRes.json() : {};
  if (!prefs.notifyLocal || !known.length) return;
  const res = await fetch('./data/tenders.json', { cache: 'no-store' });
  const data = await res.json();
  const fresh = (data.tenders || []).filter((t) => !known.includes(t.id));
  for (const t of fresh.slice(0, 5)) {
    await self.registration.showNotification(`فرصة جديدة – ${t.country_ar}`, {
      body: `${t.title}\n${t.client || ''}`.trim(), tag: t.id, dir: 'rtl', lang: 'ar',
      icon: './icons/icon-192.png', badge: './icons/badge-96.png', data: { url: `./#t-${t.id}` },
    });
  }
  if (fresh.length) {
    await meta.put('known.json', new Response(JSON.stringify((data.tenders || []).map((t) => t.id))));
  }
}

self.addEventListener('periodicsync', (e) => {
  if (e.tag === 'tr-check') e.waitUntil(backgroundCheck().catch(() => {}));
});
