/* DR Vistoria — service worker (shell cache, network-first for pages) */
const CACHE = "dr-vistoria-v1";
const PRECACHE = [
  "/static/css/mobile.css",
  "/static/js/mobile.js",
  "/static/vendor/htmx.min.js",
  "/static/mobile/icons/icon-192.png",
  "/static/mobile/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Nunca cachear mídia/uploads nem o próprio SW/manifest
  if (
    url.pathname.startsWith("/media/") ||
    url.pathname.endsWith("/sw.js") ||
    url.pathname.endsWith("manifest.webmanifest")
  ) {
    return;
  }

  // Estáticos do shell: cache-first
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
          return res;
        });
      })
    );
    return;
  }

  // HTML / rotas /m/: network-first
  if (url.pathname.startsWith("/m/")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok && req.mode === "navigate") {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then((cached) => cached || caches.match("/m/"))
        )
    );
  }
});
