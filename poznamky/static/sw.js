// Service worker: instalovatelnost PWA + offline čtení poznámek.
// Strategie:
//  - statika (CSS, ikony): cache-first
//  - HTML stránky: network-first, při výpadku připojení se podá
//    poslední známá verze z cache (hlavní stránka i navštívené poznámky)
const CACHE = 'poznamky-v6';
const STATIC = ['/static/style.css', '/static/editor.js',
                '/static/icon-192.png', '/static/icon-512.png'];

const OFFLINE_PAGE = `<!doctype html><html lang="cs"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offline – Poznámky</title>
<body style="font-family:system-ui;max-width:600px;margin:3rem auto;padding:0 1rem;color:#1f2937">
<h1>📵 Jsi offline</h1>
<p>Tahle stránka ještě není uložená v zařízení. Uložené jsou hlavní
stránka a poznámky, které jsi měl otevřené online.</p>
<p><a href="/">← Zpět na hlavní stránku</a></p></body></html>`;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // statika: cache-first
  if (STATIC.includes(url.pathname)) {
    e.respondWith(caches.match(req).then((r) => r || fetch(req)));
    return;
  }

  // HTML stránky: network-first s offline fallbackem
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((resp) => {
          // ukládat jen skutečné stránky (ne redirecty na login apod.)
          if (resp.ok && resp.type === 'basic' && !resp.redirected) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() =>
          caches.match(req).then((r) =>
            r || new Response(OFFLINE_PAGE,
                              { headers: { 'Content-Type': 'text/html; charset=utf-8' } })))
    );
  }
});
