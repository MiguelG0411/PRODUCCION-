const C='produccion-v50';const F=['./','index.html','manifest.json','icons/icon-192.png','icons/icon-512.png','icons/icon-180.png','icons/logo.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(F)));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))));self.clients.claim()});
// Primero la red; sin conexión se usa la última copia guardada (incluye los últimos datos de /api/datos)
self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||e.request.url.includes('/api/estado'))return;e.respondWith(fetch(e.request).then(r=>{if(r.ok){const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp))}return r}).catch(()=>caches.match(e.request)))});
