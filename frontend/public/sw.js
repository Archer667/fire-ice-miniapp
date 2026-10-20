const VERSION='valyria-web-v1';
const SHELL=VERSION+'-shell',ASSETS=VERSION+'-assets';
self.addEventListener('install',event=>event.waitUntil((async()=>{
  const cache=await caches.open(SHELL);
  await cache.addAll(['/offline.html','/manifest.webmanifest','/pwa/valyria-icon-192.png','/pwa/valyria-icon-512.png','/pwa/valyria-apple-180.png']);
  try{const response=await fetch('/precache.json',{cache:'no-store'});if(response.ok){const files=await response.json();await cache.addAll(files)}}catch{}
 await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const key of await caches.keys())if((key.startsWith('valyria-web-')&&!key.startsWith(VERSION+'-'))||key==='valyria-pack-files-v1'||key==='valyria-pack-meta-v1')await caches.delete(key);await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  // Account data and game actions are never cached or replayed.
  if(url.origin!==self.location.origin||request.method!=='GET'||url.pathname.startsWith('/api/'))return;
  if(url.pathname==='/map-pack.json'||url.pathname==='/map-pack-core.js'){event.respondWith(new Response('',{status:404}));return;}
  if(request.mode==='navigate'){
    event.respondWith(fetch(request).catch(()=>caches.match('/offline.html')));return;
  }
  const hashed=url.pathname.startsWith('/assets/'),font=url.pathname.startsWith('/fonts/'),map=url.pathname.startsWith('/westeros/')&&/\.(webp|png|bin|glb)$/.test(url.pathname);
  if(!hashed&&!font&&!map&&!url.pathname.startsWith('/pwa/'))return;
  event.respondWith((async()=>{
    const existing=await caches.match(request);if(existing)return existing;
    const response=await fetch(request);
    if(response.ok){const length=Number(response.headers.get('content-length'));if(!map||(length>0&&length<=2*1024*1024)){const cache=await caches.open(ASSETS);await cache.put(request,response.clone());const keys=await cache.keys();for(const key of keys.slice(0,Math.max(0,keys.length-32)))await cache.delete(key)}}
    return response;
  })());
});
