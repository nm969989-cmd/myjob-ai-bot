// tn-live-jobs/public/sw.js — Service Worker for Tamil Nadu Live Jobs

const CACHE_NAME = 'tn-live-jobs-v1';
const LOCAL_ASSETS = [
  '/tn-live-jobs/',
  '/tn-live-jobs/index.html',
  '/tn-live-jobs/manifest.json',
  '/tn-live-jobs/robots.txt',
  '/tn-live-jobs/sitemap.xml',
  '/tn-live-jobs/style.css',
  '/tn-live-jobs/app.js'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(LOCAL_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
  )).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  if (url.origin === location.origin) {
    // HTML: network-first
    if (e.request.headers.get('accept')?.includes('text/html')) {
      e.respondWith(networkFirst(e.request)); return;
    }
    // Local static: cache-first
    if (['script', 'style', 'font', 'image', 'manifest'].includes(e.request.destination)) {
      e.respondWith(cacheFirst(e.request)); return;
    }
    // Data (jobs.json, jobs.js): network-first
    if (url.pathname.includes('/data/') || e.request.headers.get('accept')?.includes('application/json')) {
      e.respondWith(networkFirst(e.request)); return;
    }
    e.respondWith(networkFirst(e.request)); return;
  }
  // Cross-origin: network only
  e.respondWith(fetch(e.request));
});

async function networkFirst(req) {
  try {
    const res = await fetch(req);
    if (res.ok) { const c = await caches.open(CACHE_NAME); c.put(req, res.clone()); }
    return res;
  } catch (err) {
    const cached = await caches.match(req);
    if (cached) return cached;
    if (req.headers.get('accept')?.includes('text/html')) return caches.match('/tn-live-jobs/');
    throw err;
  }
}

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) { const c = await caches.open(CACHE_NAME); c.put(req, res.clone()); }
    return res;
  } catch (err) { return new Response('Offline', { status: 503 }); }
}

self.addEventListener('message', (e) => { if (e.data === 'SKIP_WAITING') self.skipWaiting(); });