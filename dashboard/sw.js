// Speichert das Dashboard im Browser, damit es auch offline läuft.
// Bei Änderungen an Dateien VERSION erhöhen, dann wird neu geladen.
const VERSION = "kd-1";

const DATEIEN = [
  "./",
  "index.html",
  "style.css?v=1",
  "app.js?v=1",
  "tools/pdf.js?v=1",
  "manifest.json",
  "icons/icon.svg",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "vendor/pdf-lib.min.js",
  "vendor/pdf.min.js",
  "vendor/pdf.worker.min.js",
  "vendor/jszip.min.js"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (cache) {
    return cache.addAll(DATEIEN);
  }));
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (namen) {
    return Promise.all(namen.filter(function (n) { return n !== VERSION; }).map(function (n) {
      return caches.delete(n);
    }));
  }));
  self.clients.claim();
});

// Erst Netz (damit Updates sofort ankommen), offline aus dem Speicher
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") {
    return;
  }
  e.respondWith(fetch(e.request).then(function (antwort) {
    if (antwort.ok) {
      const kopie = antwort.clone();
      caches.open(VERSION).then(function (cache) {
        cache.put(e.request, kopie);
      });
    }
    return antwort;
  }).catch(function () {
    return caches.match(e.request);
  }));
});
