import fs from 'node:fs';
import path from 'node:path';
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
for(const name of fs.readdirSync('dist/assets'))if(/\.(js|css)$/.test(name))files.push('/assets/'+name);
for(const name of fs.readdirSync('dist/fonts'))if(/peyda-(regular|medium|semibold|bold)\.woff2$/.test(name))files.push('/fonts/'+name);
fs.writeFileSync('dist/precache.json',JSON.stringify(files));
// Every build gets independent caches; a stale worker cannot hold the current JS forever.
const sw=fs.readFileSync('dist/sw.js','utf8');
fs.writeFileSync('dist/sw.js',sw.replace('valyria-web-v1','valyria-web-'+Date.now().toString(36)));
console.log('PWA shell assets:',files.length);
