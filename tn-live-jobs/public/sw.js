// tn-live-jobs/public/sw.js — Service Worker for Tamil Nadu Live Jobs
// Caches static assets, serves offline fallback, updates on version change

const CACHE_NAME = 'tn-live-jobs-v1';
const STATIC_ASSETS = [
  '/tn-live-jobs/',
  '/tn-live-jobs/index.html',
  '/tn-live-jobs/manifest.json',
  '/tn-live-jobs/robots.txt',
  '/tn-live-jobs/sitemap.xml',
  '/tn-live-jobs/style.css',
  '/tn-live-jobs/app.js',
  '/tn-live-jobs/data/jobs.json',
  '/tn-live-jobs/data/jobs.js'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: cache-first for static assets, network-first for data
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Same-origin requests
  if (url.origin === location.origin) {
    // HTML pages: network-first with offline fallback
    if (event.request.headers.get('accept')?.includes('text/html')) {
      event.respondWith(networkFirst(event.request));
      return;
    }

    // Static assets (JS, CSS, images, fonts): cache-first
    if (event.request.destination === 'script' ||
        event.request.destination === 'style' ||
        event.request.destination === 'font' ||
        event.request.destination === 'image' ||
        event.request.destination === 'manifest') {
      event.respondWith(cacheFirst(event.request));
      return;
    }

    // API/JSON (jobs.json, jobs.js): network-first with cache fallback
    if (url.pathname.includes('/data/') || event.request.headers.get('accept')?.includes('application/json')) {
      event.respondWith(networkFirst(event.request));
      return;
    }

    // Default: network-first
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Cross-origin: network-only (Google Fonts, etc.)
  event.respondWith(fetch(event.request));
});

// Network-first strategy: try network, fall back to cache
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    // Offline fallback for HTML pages
    if (request.headers.get('accept')?.includes('text/html')) {
      return caches.match('/tn-live-jobs/');
    }
    throw err;
  }
}

// Cache-first strategy: try cache, fall back to network
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});