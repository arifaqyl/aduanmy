const CACHE = 'trafficmy-shell-v59';
const scopeUrl = new URL(self.registration.scope);
const base = scopeUrl.pathname.replace(/\/$/, '');
const shell = [
  `${base}/`,
  `${base}/static/css/tm.css?v=59`,
  `${base}/static/js/board.js?v=59`,
  `${base}/static/brand/trafficmy-mark.png`,
  `${base}/static/og-image.png`,
];

function isStyleOrScript(pathname) {
  return /\.(?:css|js)(?:\?|$)/.test(pathname);
}

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
    // CSS/JS: network-first so redesigns and fixes land without a stale shell.
    if (isStyleOrScript(url.pathname)) {
      event.respondWith(
        fetch(request)
          .then(response => {
            if (response.ok) {
              caches.open(CACHE).then(cache => cache.put(request, response.clone()));
            }
            return response;
          })
          .catch(() => caches.match(request)),
      );
      return;
    }

    event.respondWith(
      caches.match(request).then(hit => hit || fetch(request).then(response => {
        if (response.ok) caches.open(CACHE).then(cache => cache.put(request, response.clone()));
        return response;
      })),
    );
  }
});
