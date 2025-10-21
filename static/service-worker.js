// static/service-worker.js

const CACHE_NAME = 'logbook-cache-v1.6.2'; // Aggiorna la versione per forzare l'aggiornamento

const APP_SHELL_URLS = [
  '/app-shell',
  '/offline',
  '/static/style.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js',
  'https://fonts.googleapis.com/css2?family=Nunito:wght@700&display=swap'
];

self.addEventListener('install', event => {
  console.log('[Service Worker] Install...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[Service Worker] Caching app shell');
      return cache.addAll(APP_SHELL_URLS);
    })
  );
});

self.addEventListener('activate', event => {
  console.log('[Service Worker] Activate...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;

  // --- NUOVA LOGICA: Strategia differenziata ---

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
          return caches.match(request).then(response => {
            return response || caches.match('/offline');
          });
        })
    );
    return;
  }

  // 2. Per tutte le altre richieste (CSS, JS, immagini, font), usa "Cache First".
  // Questo è più efficiente per le risorse statiche che non cambiano spesso.
  event.respondWith(
    caches.match(request).then(response => {
      // Se la risorsa è in cache, restituiscila subito.
      // Altrimenti, vai alla rete.
      return response || fetch(request).then(networkResponse => {
        // Opzionale: metti in cache le nuove risorse statiche man mano che vengono richieste
        return caches.open(CACHE_NAME).then(cache => {
          cache.put(request, networkResponse.clone());
          return networkResponse;
        });
      });
    })
  );
});