import {PACK_FILES,PACK_META,PACK_ACTIVE,PACK_PENDING,packKey,validatePack} from './mapPackCore.js';

let state={phase:'idle',manifest:null,stored:0,loaded:0,done:0,total:0,error:'',persistent:false};
const listeners=new Set();let checking=null,running=null,controller=null;
const publish=values=>{state={...state,...values};listeners.forEach(fn=>fn())};
export const subscribeMapPack=fn=>{listeners.add(fn);return()=>listeners.delete(fn)};
export const getMapPack=()=>state;
const supported=()=>window.isSecureContext&&'caches'in window&&'serviceWorker'in navigator&&!!crypto.subtle;
const invalidate=()=>navigator.serviceWorker.controller?.postMessage({type:'MAP_PACK_UPDATED'});
async function savedManifest(){
 const meta=await caches.open(PACK_META);
 const response=await meta.match(PACK_PENDING)||await meta.match(PACK_ACTIVE);
 if(!response)throw new Error('برای دریافت فهرست بازی، اتصال اینترنت را بررسی کنید.');
 return validatePack(await response.json(),location.origin);
}
async function inventory(manifest){
 const cache=await caches.open(PACK_FILES),keys=new Set((await cache.keys()).map(request=>request.url));
 const present=manifest.files.filter(file=>keys.has(packKey(file,location.origin)));
 return {stored:present.reduce((n,file)=>n+file.bytes,0),done:present.length,keys};
}
export async function inspectMapPack(){
 if(running)return state;
 if(checking)return checking;
 checking=(async()=>{
  if(!supported()){publish({phase:'unsupported',error:'برای دریافت فایل‌های بازی، لینک را در Chrome یا Safari به‌روز باز کنید.'});return state}
  publish({phase:'checking',error:''});
  try{
   let manifest;
   try{
    const response=await fetch('/map-pack.json',{cache:'no-store'});
    if(!response.ok)throw new Error();
    manifest=validatePack(await response.json(),location.origin);
    const meta=await caches.open(PACK_META);await meta.put(PACK_PENDING,new Response(JSON.stringify(manifest),{headers:{'Content-Type':'application/json'}}));
   }catch{manifest=await savedManifest()}
   const current=await inventory(manifest),ready=current.done===manifest.files.length;
   publish({phase:ready?'ready':'idle',manifest,stored:current.stored,loaded:current.stored,done:current.done,total:manifest.files.length,error:''});
   if(ready)await activatePack(manifest);
  }catch(error){publish({phase:'error',error:error.message||'دریافت فهرست بازی انجام نشد؛ دوباره تلاش کنید.'})}
  return state;
 })().finally(()=>{checking=null});
 return checking;
}
async function ensureWorker(){
 const reg=await navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'});
 const activate=()=>reg.waiting?.postMessage({type:'ACTIVATE_MAP_PACK_WORKER'});
 activate();
 if(reg.installing)reg.installing.addEventListener('statechange',activate);
 reg.addEventListener('updatefound',()=>reg.installing?.addEventListener('statechange',activate),{once:true});
 await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(new Error('آماده‌سازی ذخیره‌سازی طول کشید؛ صفحه را تازه کنید.')),15000))]);
 for(let i=0;i<20;i++){
  activate();
  const worker=navigator.serviceWorker.controller;
  if(worker){
   const ready=await new Promise(resolve=>{const channel=new MessageChannel();const timer=setTimeout(()=>{channel.port1.close();resolve(false)},500);channel.port1.onmessage=e=>{clearTimeout(timer);channel.port1.close();resolve(e.data?.mapPack===1)};worker.postMessage({type:'MAP_PACK_PING'},[channel.port2])});
   if(ready)return;
  }
  await new Promise(resolve=>setTimeout(resolve,250));
 }
 throw new Error('نسخهٔ ذخیره‌سازی بازی هنوز آماده نیست؛ صفحه را تازه کنید و دوباره تلاش کنید.');
}
async function activatePack(manifest){
 const meta=await caches.open(PACK_META);
 await meta.put(PACK_ACTIVE,new Response(JSON.stringify(manifest),{headers:{'Content-Type':'application/json'}}));
 invalidate();
 // Keep pack data independent of shell updates; remove only superseded pack entries.
 const keep=new Set(manifest.files.map(file=>packKey(file,location.origin))),cache=await caches.open(PACK_FILES);
 for(const request of await cache.keys())if(!keep.has(request.url))await cache.delete(request);
 await caches.delete('valyria-map-hybrid-v2');
}
export async function downloadMapPack(){
 if(running)return running;
 if(!state.manifest||state.phase==='error')await inspectMapPack();
 if(running)return running;
 if(!state.manifest||!supported())return;
 controller=new AbortController();const signal=controller.signal;
 running=(async()=>{
  try{
   publish({phase:'downloading',error:''});
   const persistent=await navigator.storage?.persist?.().catch(()=>false)||false;
   publish({persistent});
   await ensureWorker();
   const manifest=state.manifest,current=await inventory(manifest);
   const missing=manifest.files.filter(file=>!current.keys.has(packKey(file,location.origin)));
   const estimate=await navigator.storage?.estimate?.().catch(()=>null);
   if(estimate?.quota&&estimate.quota-(estimate.usage||0)<(manifest.bytes-current.stored)*1.15)throw new Error('فضای آزاد کافی نیست؛ کمی از حافظهٔ گوشی را خالی کنید و دوباره بزنید.');
   let stored=current.stored,done=current.done,next=0;const active=new Map(),cache=await caches.open(PACK_FILES);
   let lastProgress=0;
   const progress=(force=false)=>{if(!force&&Date.now()-lastProgress<120)return;lastProgress=Date.now();publish({stored,loaded:stored+[...active.values()].reduce((a,b)=>a+b,0),done,total:manifest.files.length})};
   progress(true);
   async function worker(){
    while(next<missing.length){
     if(signal.aborted)throw new DOMException('Paused','AbortError');
     const file=missing[next++];active.set(file.url,0);
     const response=await fetch(file.url,{cache:'reload',credentials:'omit',headers:{'X-Valyria-Pack-Download':'1'},signal});
     if(!response.ok||!response.body)throw new Error('دریافت یکی از فایل‌ها قطع شد؛ برای ادامه دوباره بزنید.');
     const reader=response.body.getReader(),chunks=[];let length=0;
     for(;;){const chunk=await reader.read();if(chunk.done)break;chunks.push(chunk.value);length+=chunk.value.byteLength;active.set(file.url,length);progress();if(length>file.bytes)throw new Error('فایل دریافت‌شده با نسخهٔ بازی مطابقت ندارد؛ صفحه را تازه کنید.')}
     if(length!==file.bytes)throw new Error('یکی از فایل‌ها ناقص دریافت شد؛ دوباره تلاش کنید.');
     const bytes=new Uint8Array(length);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength}
     const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
     if(hash!==file.sha256)throw new Error('نسخهٔ یکی از فایل‌ها تغییر کرده است؛ فهرست بازی را تازه کنید و دوباره بزنید.');
     if(signal.aborted)throw new DOMException('Paused','AbortError');
     await cache.put(packKey(file,location.origin),new Response(bytes,{headers:{'Content-Type':response.headers.get('Content-Type')||'application/octet-stream','Content-Length':String(length)}}));
     stored+=file.bytes;done++;active.delete(file.url);progress(true);
    }
   }
   const result=await Promise.allSettled([worker(),worker()].map(p=>p.catch(error=>{controller.abort();throw error})));
   const failure=result.find(item=>item.status==='rejected'&&item.reason.name!=='AbortError')||result.find(item=>item.status==='rejected');
   if(failure)throw failure.reason;
   await activatePack(manifest);publish({phase:'ready',stored:manifest.bytes,loaded:manifest.bytes,done:manifest.files.length,error:''});
  }catch(error){
   const current=await inventory(state.manifest).catch(()=>({stored:state.stored,done:state.done}));
   publish({phase:error.name==='AbortError'?'paused':'error',stored:current.stored,loaded:current.stored,done:current.done,error:error.name==='AbortError'?'':error.name==='QuotaExceededError'?'حافظهٔ کافی در دسترس نیست؛ فضای گوشی را بررسی کنید.':error.message||'دریافت قطع شد؛ برای ادامه دوباره بزنید.'});
  }finally{running=null;controller=null}
 })();
 return running;
}
export function pauseMapPack(){controller?.abort()}
