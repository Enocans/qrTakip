const CACHE = 'pusula-shell-v3-mobile';
const ASSETS = ['/', '/static/app.css?v=3', '/static/app.js?v=3', '/static/icon.svg', '/static/icon-192.png', '/static/icon-512.png', '/static/manifest.webmanifest'];
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('pusula-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())); });
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/')||url.pathname==='/download'||url.pathname==='/qr')return;
  if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request).catch(()=>caches.match('/')));return;
  }
  if(ASSETS.includes(url.pathname+url.search))event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));
});
