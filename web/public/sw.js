// ThinkBuddy Service Worker - Shell & Today's Plan Cache
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

// Logout purge message listener (P08 deliverable: no authenticated data left in SW caches)
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "LOGOUT_PURGE") {
    event.waitUntil(
      caches.keys().then((keys) => {
        return Promise.all(
          keys.map((key) => caches.delete(key))
        );
      }).then(() => {
        // Re-cache only anonymous static assets shell
        return caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS));
      })
    );
  }
});

self.addEventListener("fetch", (event) => {
  // Offline caching strategy for Today's plan
  if (event.request.url.includes("/api/proxy/students/") && event.request.url.includes("/today")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const resClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, resClone);
          });
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Stale-while-revalidate for static navigation
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
