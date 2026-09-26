// Project S.M.I.L.E. - DepEd Parent Mobile App Service Worker
const CACHE_NAME = 'smile-parent-v5';
const STATIC_ASSETS = [
  '/parent',
  '/static/manifest.json',
  '/static/images/pwa_icon_192.png',
  '/static/images/pwa_icon_512.png',
  '/static/images/apple_touch_icon.png',
  '/static/images/deped_seal.svg',
  '/static/audio/gate_alert.wav',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

// 1. Install & Pre-cache App Shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.log('[SW] Cache prefetch note:', err);
      });
    })
  );
  self.skipWaiting();
});

// 2. Activate & Purge Stale Caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => clients.claim())
  );
});

// 3. Network-First with Offline Cache Fallback
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Allow API and dynamic poll endpoints to bypass cache
  if (url.pathname.startsWith('/api/') || event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          if (event.request.mode === 'navigate') {
            return caches.match('/parent');
          }
        });
      })
  );
});

// 4. Instant Real-Time Push Notification Engine
self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "New Gate Attendance Event" };
  }

  const title = data.title || "DepEd Project S.M.I.L.E. Alert";
  const options = {
    body: data.body || "Your child has passed through the school gate.",
    icon: data.icon || "/static/images/pwa_icon_192.png",
    badge: "/static/images/pwa_icon_192.png",
    image: data.image || null,
    vibrate: [500, 150, 500, 150, 500],
    tag: data.tag || ('gate-' + Date.now()),
    renotify: true,
    requireInteraction: true,
    silent: false,
    sound: '/static/audio/gate_alert.wav',
    data: {
      url: data.url || '/parent',
      timestamp: Date.now(),
      lrn: data.lrn || ''
    },
    actions: [
      { action: 'open_app', title: '👁️ View Gate Scan' },
      { action: 'close', title: '✕ Dismiss' }
    ]
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// 5. Handle Notification Click Navigation
self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'close') return;

  const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/parent';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      // Focus existing window if open
      for (let client of windowClients) {
        if (client.url.includes('/parent') && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
