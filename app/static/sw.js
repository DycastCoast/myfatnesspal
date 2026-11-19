// Service worker: makes the app installable and keeps styles/icons cached so it opens fast.
// Pages themselves always come from the network, so you never see a stale diary.
// Bump VERSION whenever app.css / scan.js / icons change, so phones fetch the new ones.
const VERSION = 'mfp-v1';
const STATIC = ['/static/app.css', '/static/scan.js', '/static/icons/icon-192.png'];

self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(STATIC); }).catch(function () {}));
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }));
  self.clients.claim();
});

self.addEventListener('fetch', function (event) {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    // Cache first for static files.
    event.respondWith(caches.match(event.request).then(function (hit) {
      return hit || fetch(event.request).then(function (res) {
        const copy = res.clone();
        caches.open(VERSION).then(function (c) { c.put(event.request, copy); });
        return res;
      });
    }));
    return;
  }

  if (event.request.mode === 'navigate') {
    // Network for pages; a friendly message if there's no signal.
    event.respondWith(fetch(event.request).catch(function () {
      return new Response(
        '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<body style="font-family:system-ui;padding:40px;text-align:center">' +
        '<h1>You\'re offline</h1><p>Logging needs a connection. Try again when you\'re back online.</p></body>',
        { headers: { 'Content-Type': 'text/html' } });
    }));
  }
});
