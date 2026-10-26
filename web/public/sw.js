// ThinkBuddy Service Worker - Shell Cache & Secure Network Isolation
const CACHE_NAME = "tb-cache-v1";
const STATIC_ASSETS = ["/", "/manifest.json", "/globals.css"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Purge cache on logout, session expiry, or 401 response
function purgeAllCaches() {
  return caches.keys().then((keys) => {
    return Promise.all(keys.map((key) => caches.delete(key)));
  }).then(() => {
    return caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS));
  });
}

self.addEventListener("message", (event) => {
  if (
    event.data &&
    (event.data.type === "LOGOUT_PURGE" ||
      event.data.type === "SESSION_EXPIRED" ||
      event.data.type === "AUTH_401_PURGE")
  ) {
    event.waitUntil(purgeAllCaches());
  }
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Network-only for /api/* with automatic cache purge on 401 (Item 5)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).then((response) => {
        if (response.status === 401) {
          purgeAllCaches();
        }
        return response;
      })
    );
    return;
  }

  // Stale-while-revalidate for static shell assets only
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
