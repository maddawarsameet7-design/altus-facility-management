// Deployment Version Identifier: Update with each release to invalidate stale app caches
const CACHE_VERSION = '2026.11.04.1';
const CACHE_NAME = `altsan-pwa-v${CACHE_VERSION}`;
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Security & Data Freshness: Never cache API requests, WebSocket handshakes, or mutations.
  // Network-only policy ensures auth tokens, financial data, and credentials bypass cache.
  if (
    url.pathname.startsWith('/api/') || 
    url.pathname.startsWith('/ws/') || 
    event.request.method !== 'GET'
  ) {
    return; // Passthrough directly to network
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Push notification listener
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Altsan Notification';
  const options = {
    body: data.body || 'You have a new update in the Altsan Platform.',
    icon: '/logo192.png',
    badge: '/logo192.png'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});
