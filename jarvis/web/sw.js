/* JARVIS service worker — makes the app installable and usable offline.
 *
 * Strategy:
 *  - API and non-GET traffic is never intercepted (auth, streaming, mutations
 *    always hit the network untouched).
 *  - App navigations are network-first, falling back to the cached shell when
 *    offline so the app still opens.
 *  - Static assets are served cache-first and refreshed in the background
 *    (stale-while-revalidate), so a new deploy is picked up on the next load.
 *
 * Bump CACHE to force every client to drop old cached assets.
 */
const CACHE = "jarvis-v1";
const SHELL = [
  "/",
  "/static/css/app.css",
  "/static/js/api.js",
  "/static/js/ui.js",
  "/static/js/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin GETs. Leave API/auth/streaming untouched.
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }

  // App shell navigations: fresh when online, cached shell when offline.
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/")));
    return;
  }

  // Static assets: cache-first, revalidate in the background.
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((resp) => {
          if (resp && resp.ok) {
            const copy = resp.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
