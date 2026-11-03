// Deployment Version Identifier: Update with each release to invalidate stale app caches
const CACHE_VERSION = '2026.11.04.2';
const CACHE_NAME = `altsan-pwa-v${CACHE_VERSION}`;
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json'
];

self.addEventListener('install', event => {
  self.skipWaiting();
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

  // For HTML / navigation requests, use Network-First to ensure new deploys are loaded immediately
  if (event.request.mode === 'navigate' || event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // For static assets, Cache-First with network fallback
  event.respondWith(
    caches.match(event.request)
      .then(response => {
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
    }).then(() => self.clients.claim())
  );
});

// Push notification listener
self.addEventListener('push', event => {
  if (!event.data) return;
  try {
    const data = event.data.json();
    const title = data.title || 'Altsan Notification';
    const options = {
      body: data.body || '',
      icon: '/icons/icon-192x192.png',
      badge: '/icons/icon-192x192.png',
      data: { url: data.url || '/' }
    };
    event.waitUntil(self.registration.showNotification(title, options));
  } catch (e) {
    console.error('Push handling error:', e);
  }
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
