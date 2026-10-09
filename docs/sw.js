// docs/sw.js — Service Worker for MyJob AI Radar
// Caches local assets only, network-first for HTML, cache-first for local static

const CACHE_NAME = 'myjob-radar-v1';
const LOCAL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/robots.txt',
  '/sitemap.xml'
];

// Install: cache local assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(LOCAL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

// Fetch: network-first for HTML, cache-first for local static, network for cross-origin
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;

  // Same-origin
  if (url.origin === location.origin) {
    // HTML: network-first with offline fallback
    if (event.request.headers.get('accept')?.includes('text/html')) {
      event.respondWith(networkFirst(event.request));
      return;
    }
    // Local static (JS, CSS, fonts, images, manifest): cache-first
    if (['script', 'style', 'font', 'image', 'manifest'].includes(event.request.destination)) {
      event.respondWith(cacheFirst(event.request));
      return;
    }
    // API/JSON: network-only
    if (url.pathname.startsWith('/api/') || event.request.headers.get('accept')?.includes('application/json')) {
      return; // pass through to network
    }
    event.respondWith(networkFirst(event.request));
    return;
  }
  // Cross-origin: pass through to network (Google Fonts, Tailwind CDN, Lucide, Telegram)
  event.respondWith(fetch(event.request));
});

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
    if (request.headers.get('accept')?.includes('text/html')) {
      return caches.match('/');
    }
    throw err;
  }
}

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
    return new Response('Offline', { status: 503 });
  }
}

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});