// docs/sw.js — Service Worker for MyJob AI Radar
// Caches static assets, serves offline fallback, updates on version change

const CACHE_NAME = 'myjob-radar-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/robots.txt',
  '/sitemap.xml',
  // External CDN resources we want to cache
  'https://cdn.tailwindcss.com/3.4.16',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@500;600;700;800;900&display=swap',
  'https://unpkg.com/lucide@0.469.0/dist/umd/lucide.min.js',
  'https://telegram.org/js/telegram-web-app.js'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Cache local assets
      return cache.addAll(STATIC_ASSETS.filter(url => url.startsWith('/')));
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

// Fetch: network-first for HTML, cache-first for static assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip Telegram SDK (cross-origin, no caching needed)
  if (url.origin === 'https://telegram.org') return;

  // Skip SimplifyJobs GitHub raw (always fetch fresh)
  if (url.origin === 'https://raw.githubusercontent.com' && url.pathname.includes('SimplifyJobs')) {
    return;
  }

  // Handle same-origin requests
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
        event.request.destination === 'image') {
      event.respondWith(cacheFirst(event.request));
      return;
    }

    // API/JSON: network-only (always fresh)
    if (url.pathname.startsWith('/api/') || event.request.headers.get('accept')?.includes('application/json')) {
      event.respondWith(fetch(event.request));
      return;
    }

    // Default: network-first
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Cross-origin CDN resources: cache-first with network fallback
  if (STATIC_ASSETS.some(asset => event.request.url.startsWith(asset))) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // Default: network-only for other cross-origin
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
      return caches.match('/');
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
    // Return a minimal offline response
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

// Handle messages from clients (e.g., skipWaiting)
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});