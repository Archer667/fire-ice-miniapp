importScripts('/map-pack-core.js');
const {PACK_FILES,PACK_META,PACK_ACTIVE,PACK_PENDING,packKey,validatePack}=self.ValyriaPack;
let packIndex=null;
async function packResponse(url){
 try{
  if(!packIndex)packIndex=(async()=>{const meta=await caches.open(PACK_META);const response=await meta.match(PACK_ACTIVE)||await meta.match(PACK_PENDING);if(!response)return null;const manifest=validatePack(await response.json(),self.location.origin);return new Map(manifest.files.map(file=>[new URL(file.url,self.location.origin).pathname,file]))})();
  const index=await packIndex,file=index?.get(url.pathname);
  if(file)return(await caches.open(PACK_FILES)).match(packKey(file,self.location.origin));
 }catch{packIndex=null}
 return null;
}
self.addEventListener('message',event=>{
 if(event.data?.type==='MAP_PACK_UPDATED')packIndex=null;
 if(event.data?.type==='MAP_PACK_PING')event.ports[0]?.postMessage({mapPack:1});
 if(event.data?.type==='ACTIVATE_MAP_PACK_WORKER')self.skipWaiting();
});
const VERSION='valyria-web-v1';
const SHELL=VERSION+'-shell',ASSETS=VERSION+'-assets';
self.addEventListener('install',event=>event.waitUntil((async()=>{
  const cache=await caches.open(SHELL);
  await cache.addAll(['/offline.html','/manifest.webmanifest','/map-pack-core.js','/pwa/valyria-icon-192.png','/pwa/valyria-icon-512.png','/pwa/valyria-apple-180.png']);
  try{const response=await fetch('/precache.json',{cache:'no-store'});if(response.ok){const files=await response.json();await cache.addAll(files)}}catch{}
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{for(const key of await caches.keys())if(key.startsWith('valyria-web-')&&!key.startsWith(VERSION+'-'))await caches.delete(key);await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  // Account data and game actions are never cached or replayed.
  if(url.origin!==self.location.origin||request.method!=='GET'||url.pathname.startsWith('/api/'))return;
  if(request.headers.get('X-Valyria-Pack-Download')==='1'||url.pathname==='/map-pack.json')return;
  const packAsset=/^\/(?:westeros\/hybrid-v2|fonts|icons|institutions|buildings|maps|pwa)\//.test(url.pathname);
  if(packAsset&&!request.headers.has('range')){
    event.respondWith((async()=>{const local=await packResponse(url);if(local)return local;return fetch(request)})());return;
  }
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
