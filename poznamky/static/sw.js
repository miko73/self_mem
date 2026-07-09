// Minimální service worker – vyžadován pro instalovatelnost PWA.
// Data nekešuje (poznámky musí být vždy aktuální), jen statiku.
const CACHE = 'poznamky-static-v1';
const STATIC = ['/static/style.css', '/static/icon-192.png', '/static/icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (STATIC.includes(url.pathname)) {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
  }
  // ostatní požadavky jdou přímo na síť
});
