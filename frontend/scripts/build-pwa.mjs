import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
const files=[];
function checkDistribution(folder){
  for(const entry of fs.readdirSync(folder,{withFileTypes:true})){
    const item=path.join(folder,entry.name);
    if(entry.isDirectory()){
      if(['.git','node_modules','backend','src'].includes(entry.name))throw new Error('Private development directory in web distribution: '+item);
      checkDistribution(item);
    }else if(/\.map$|\.py$|^\.env(?:\.|$)/i.test(entry.name))throw new Error('Private development file in web distribution: '+item);
  }
}
checkDistribution('dist');
// This complete asset pack is independent of the frequently updated app shell.
const packFiles=[];
const mapBase='westeros/hybrid-v2/';
function includePack(relative){
  if(relative.startsWith(mapBase)){
    const name=relative.slice(mapBase.length);
    return /^(?:tiles|castles|flag-uv|north-snow)\//.test(name)||/^(?:index-profile\.html|manifest\.json|review-data\.json|army-models\.js|weather-effects\.js|north-landmarks\.js|map-performance\.js|map-runtime-profile\.js|castle-worker-profile\.js|runtime-profile-\d+\.bin|overview-\d+\.webp)$/.test(name);
  }
  return /^(?:icons|institutions|buildings|fonts|maps|pwa)\//.test(relative)&&/\.(?:webp|png|jpe?g|avif|svg|woff2?)$/.test(relative);
}
function addPack(folder){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){
  const filename=path.join(folder,entry.name);
  if(entry.isDirectory())addPack(filename);
  else {const relative=path.relative('dist',filename).split(path.sep).join('/');if(includePack(relative)){
    const bytes=fs.readFileSync(filename);packFiles.push({url:encodeURI('/'+relative),bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});
  }}
}}
addPack('dist');packFiles.sort((a,b)=>a.url.localeCompare(b.url,'en'));
const pack={schema:1,version:crypto.createHash('sha256').update(JSON.stringify(packFiles)).digest('hex'),bytes:packFiles.reduce((n,file)=>n+file.bytes,0),files:packFiles};
fs.writeFileSync('dist/map-pack.json',JSON.stringify(pack));
const core=fs.readFileSync('src/mapPackCore.js','utf8').replace(/^export /gm,'');
fs.writeFileSync('dist/map-pack-core.js',`(()=>{${core}\nself.ValyriaPack={PACK_FILES,PACK_META,PACK_ACTIVE,PACK_PENDING,packKey,validatePack};})();`);
console.log('Downloadable map pack:',pack.files.length,'files,',(pack.bytes/1024/1024).toFixed(1),'MiB');
for(const name of fs.readdirSync('dist/assets'))if(/\.(js|css)$/.test(name))files.push('/assets/'+name);
for(const name of fs.readdirSync('dist/fonts'))if(/peyda-(regular|medium|semibold|bold)\.woff2$/.test(name))files.push('/fonts/'+name);
fs.writeFileSync('dist/precache.json',JSON.stringify(files));
// Every build gets independent caches; a stale worker cannot hold the current JS forever.
const sw=fs.readFileSync('dist/sw.js','utf8');
fs.writeFileSync('dist/sw.js',sw.replace('valyria-web-v1','valyria-web-'+Date.now().toString(36)));
console.log('PWA shell assets:',files.length);
