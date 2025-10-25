// static/service-worker.js

// Aggiorna questa versione ogni volta che fai una modifica significativa ai file in cache
const CACHE_NAME = 'logbook-cache-v1.9.7.2'; 

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
self.addEventListener('fetch', event => {
  const { request } = event;

  // 1. Per la navigazione HTML (pagine del sito), usa la strategia "Network First".
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Se la rete risponde, metti in cache la nuova pagina e restituiscila
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(request, response.clone());
            return response;
          });
        })
        .catch(() => {
          // Se la rete fallisce (offline), cerca una corrispondenza nella cache
          // o mostra la pagina offline di fallback.
          return caches.match(request).then(response => {
            return response || caches.match('/offline');
          });
        })
    );
    return;
  }

  // 2. Per tutte le altre richieste (CSS, JS, immagini, font), usa "Cache First".
  event.respondWith(
    caches.open(CACHE_NAME).then(cache => {
      // --- MODIFICA QUI: Ignora i parametri di query (es. ?v=1.9.7) per il matching ---
      return cache.match(request, { ignoreSearch: true }).then(response => {
        // Se la risorsa è in cache, restituiscila subito.
        // Altrimenti, vai alla rete.
        return response || fetch(request).then(networkResponse => {
          // Opzionale: metti in cache le nuove risorse statiche man mano che vengono richieste
          cache.put(request, networkResponse.clone());
          return networkResponse;
        });
      });
    })
  );
});