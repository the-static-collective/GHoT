/* Static read-only UI caching. No network synchronization, mailboxes or money. */
const CACHE="postemahhn-carrier-pocket-003-v1";
const ASSETS=["./","./index.html","./two-phones.html","./two-phone-core.js","./vendor/qrgen.min.js","./manifest.webmanifest"];
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(
    keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))
  )));
  self.clients.claim();
});
self.addEventListener("fetch",event=>{
  const req=event.request;
  if(req.method!=="GET"||new URL(req.url).origin!==self.location.origin)return;
  event.respondWith(caches.match(req).then(hit=>hit||fetch(req)));
});
