const CACHE = 'trafficmy-shell-v26';
const scopeUrl = new URL(self.registration.scope);
const base = scopeUrl.pathname.replace(/\/$/, '');
const shell = [
  `${base}/`,
  `${base}/static/logo.svg`,
  `${base}/static/favicon.svg`,
  `${base}/static/icon-512.png`,
  `${base}/static/og-image.png`,
  `${base}/static/css/play.css`,
  `${base}/static/css/stitch.css`,
  `${base}/static/lines/kv-system.svg`,
  `${base}/static/js/app.js`,
  `${base}/static/mascots/stitch-mascot.png`,
  `${base}/static/mascots/stitch-mascot-worried.png`,
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(shell)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== location.origin || url.pathname.includes('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE).then(cache => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then(hit => hit || caches.match(`${base}/`))),
    );
    return;
  }

  if (url.pathname.includes('/static/')) {
    event.respondWith(
      caches.match(request).then(hit => hit || fetch(request).then(response => {
        if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
        return response;
      })),
    );
  }
});
