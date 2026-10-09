/* Public-site offline shell only. Never cache authentication or API responses. */
'use strict';
const PREFIX = 'myjob-career-' + encodeURIComponent(self.registration.scope) + '-';
const CACHE = PREFIX + '81dab4cd74ce';
const FILES = ['offline.html', 'career/core.js', 'career/workspace.js', 'career/workspace.css', 'manifest.webmanifest', 'career/icon-192.png', 'career/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES.map(file => new URL(file, self.registration.scope).href))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith(PREFIX) && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  const base = new URL(self.registration.scope);
  if (request.method !== 'GET' || url.origin !== base.origin || !url.pathname.startsWith(base.pathname) || [...url.searchParams.keys()].some(k => /^(token|auth|session|key)$/i.test(k)) || /\/api\/|\/career-assets\//.test(url.pathname)) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.open(CACHE).then(cache => cache.match(new URL('offline.html', base).href))));
  } else if (FILES.some(file => url.href === new URL(file, base).href)) {
    event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(request)) || fetch(request)));
  }
});
