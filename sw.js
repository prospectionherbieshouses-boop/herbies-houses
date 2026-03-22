// Service Worker — Herbies Houses
// Stratégie : cache-first pour l'app shell, network-first pour l'API

const CACHE_NAME = 'herbies-v1';
const APP_SHELL  = ['/', '/index.html', '/manifest.json', '/icon-192.svg'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Requêtes API — network-first, pas de cache
  if (url.pathname.startsWith('/listings') || url.pathname.startsWith('/scrape') || url.pathname.startsWith('/analyze')) {
    event.respondWith(fetch(event.request).catch(() => new Response('{"error":"offline"}', { headers: { 'Content-Type': 'application/json' } })));
    return;
  }

  // App shell — cache-first
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
