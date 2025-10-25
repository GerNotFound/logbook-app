// static/service-worker.js

// Aggiorna questa versione ogni volta che fai una modifica significativa ai file in cache
const CACHE_NAME = 'logbook-cache-v1.9.8';

// Lista dei file fondamentali per l'app shell
const APP_SHELL_URLS = [
  '/',
  '/app-shell',
  '/offline',
  
  // --- MODIFICA QUI: Allineamento e aggiunta di risorse ---
  // CSS
  '/static/style.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  
  // JAVASCRIPT
  '/static/js/app.js',
  '/static/js/service-worker-registration.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',

  // FONT (Bootstrap Icons richiede questo)
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2?dd67030699838ea613ee6dbda9032279',
  
  // IMMAGINI PWA
  '/static/icon-512x512.png',
  '/static/apple-touch-icon.png'
];

// Evento di installazione: scarica e mette in cache l'app shell
self.addEventListener('install', event => {
  console.log('[Service Worker] Install...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Caching app shell');
        return cache.addAll(APP_SHELL_URLS);
      })
      .then(() => {
        // --- NUOVO: Forza l'attivazione del nuovo Service Worker ---
        return self.skipWaiting();
      })
  );
});

// Evento di attivazione: pulisce le vecchie cache
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activate...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    }).then(() => {
      // --- NUOVO: Prende il controllo immediato della pagina ---
      return self.clients.claim();
    })
  );
});

// Evento fetch: intercetta le richieste di rete
function shouldCacheResponse(request, response) {
  return response && response.ok && request.method === 'GET';
}

function cacheFirst(request) {
  return caches.open(CACHE_NAME).then((cache) =>
    cache.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(request)
        .then((networkResponse) => {
          if (shouldCacheResponse(request, networkResponse)) {
            cache.put(request, networkResponse.clone());
          }
          return networkResponse;
        })
        .catch(() => cache.match(request, { ignoreSearch: true }));
    })
  );
}

function networkFirst(request, offlineFallback) {
  return caches.open(CACHE_NAME).then((cache) =>
    fetch(request)
      .then((networkResponse) => {
        if (shouldCacheResponse(request, networkResponse)) {
          cache.put(request, networkResponse.clone());
        }
        return networkResponse;
      })
      .catch(() => cache.match(request).then((cached) => cached || (offlineFallback ? caches.match(offlineFallback) : cache.match(request, { ignoreSearch: true }))))
  );
}

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, '/offline'));
    return;
  }

  const requestUrl = new URL(request.url);

  if (requestUrl.origin === self.location.origin && requestUrl.pathname.startsWith('/static/js/sessione_palestra')) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(cacheFirst(request));
});
