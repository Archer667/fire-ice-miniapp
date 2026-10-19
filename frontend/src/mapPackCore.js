export const PACK_FILES='valyria-pack-files-v1';
export const PACK_META='valyria-pack-meta-v1';
export const PACK_ACTIVE='/__valyria_pack_active__';
export const PACK_PENDING='/__valyria_pack_pending__';

export function packKey(file,origin){
 const url=new URL(file.url,origin);url.search='?__valyria_pack='+file.sha256;return url.href;
}
export function validatePack(raw,origin){
 if(raw?.schema!==1||!Array.isArray(raw.files)||!raw.files.length||raw.files.length>10000||!/^[a-f0-9]{64}$/.test(raw.version||''))throw new Error('فهرست فایل‌های بازی معتبر نیست.');
 const seen=new Set();let bytes=0;
 for(const file of raw.files){
  const url=new URL(file.url,origin);
  if(url.origin!==origin||url.search||url.hash||!/^\/(?:westeros\/hybrid-v2|fonts|icons|institutions|buildings|maps|pwa)\//.test(url.pathname)||!/\.(?:cpack|bin|webp|png|jpe?g|avif|svg|js|json|html|woff2?|glb)$/.test(url.pathname)||!Number.isSafeInteger(file.bytes)||file.bytes<0||!/^[a-f0-9]{64}$/.test(file.sha256||'')||seen.has(url.pathname))throw new Error('یکی از فایل‌های بستهٔ بازی معتبر نیست.');
  seen.add(url.pathname);bytes+=file.bytes;
 }
 if(raw.bytes!==bytes)throw new Error('حجم بسته با فهرست فایل‌ها مطابقت ندارد.');
 return raw;
}

