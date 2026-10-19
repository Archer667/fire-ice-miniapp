import {useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {createPortal} from 'react-dom';
import {subscribeMapPack,getMapPack,inspectMapPack,downloadMapPack,pauseMapPack} from './mapPack.js';

// Capture the browser event before account checks or sign-in finish.
let installEvent=null;
let guideRequested=new URLSearchParams(location.search).get('install')==='1';
let installed=window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
const listeners=new Set();
const notify=()=>listeners.forEach(fn=>fn());
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installEvent=event;notify()});
window.addEventListener('appinstalled',()=>{installed=true;installEvent=null;notify()});

export default function InstallApp({header=false}){
 const [open,setOpen]=useState(()=>{const requested=guideRequested;guideRequested=false;return requested});
 const [,refresh]=useState(0),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const apple=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 const [platform,setPlatform]=useState(apple?'ios':'android');
 const pack=useSyncExternalStore(subscribeMapPack,getMapPack);
 const downloading=pack.phase==='downloading',checking=pack.phase==='checking';
 const size=n=>(n/1024/1024).toLocaleString('fa-IR',{maximumFractionDigits:1})+' مگابایت';
 const percent=pack.manifest?Math.min(100,Math.floor(pack.loaded/pack.manifest.bytes*100)):0;
 useEffect(()=>{if(open)inspectMapPack()},[open]);
 const dialog=useRef(null),trigger=useRef(null);
 useEffect(()=>{const fn=()=>refresh(v=>v+1);listeners.add(fn);return()=>listeners.delete(fn)},[]);
 useEffect(()=>{
  if(!open)return;
  const previous=document.activeElement;
  dialog.current?.querySelector('button')?.focus();
  const key=e=>{
   if(e.key==='Escape'){setOpen(false);return}
   if(e.key!=='Tab')return;
   const controls=[...dialog.current.querySelectorAll('button:not(:disabled),a[href],[tabindex="0"]')];
   const first=controls[0],last=controls.at(-1);
   if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}
   else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}
  };
  document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('keydown',key);previous?.focus()};
 },[open]);

 const install=async()=>{
  const event=installEvent;if(!event)return;
  installEvent=null;setBusy(true);setMessage('');
  try{await event.prompt();const choice=await event.userChoice;if(choice.outcome==='accepted')setOpen(false);else setMessage('نصب انجام نشد؛ هر زمان بخواهید می‌توانید دوباره از منوی مرورگر نصب کنید.')}
  catch{setMessage('نصب را از منوی مرورگر انجام دهید؛ راهنمای دستگاه شما در پایین آمده است.')}
  finally{setBusy(false);notify()}
 };
 return <>
  <button ref={trigger} type="button" className={header?'rbtn web-install-trigger':'btn ghost web-install-login'} onClick={()=>setOpen(true)}>{installed?'فایل‌های نقشه':'دانلود و نصب برنامه'}</button>
  {open&&createPortal(<div className="web-modal web-install-overlay" onClick={e=>{if(e.target===e.currentTarget)setOpen(false)}}>
   <section ref={dialog} className="card web-install-card" role="dialog" aria-modal="true" aria-labelledby="install-title" dir="rtl">
    <button type="button" className="rbtn web-install-close" aria-label="بستن راهنمای نصب" onClick={()=>setOpen(false)}>×</button>
    <img className="web-install-icon" src="/pwa/valyria-icon-192.png" alt="نشان والریا" width="88" height="88"/>
    <span className="web-install-eyebrow">والریا همیشه همراه شما</span>
    <h2 id="install-title" dir="ltr">Valyria Web App</h2>
    <p className="page-sub">مدل‌های سه‌بعدی و تصاویر را یک‌بار دریافت کنید تا در مراجعه‌های بعد از حافظهٔ دستگاه بارگذاری شوند.</p>
    <div className="grid2 web-install-tabs" role="group" aria-label="نوع گوشی">
     <button type="button" className={'btn '+(platform==='android'?'':'ghost')} aria-pressed={platform==='android'} onClick={()=>setPlatform('android')}>اندروید</button>
     <button type="button" className={'btn '+(platform==='ios'?'':'ghost')} aria-pressed={platform==='ios'} onClick={()=>setPlatform('ios')}>آیفون و آیپد</button>
    </div>
    <div className="web-pack-card">
     <h3>۱. دریافت فایل‌های بازی</h3>
     <p className="web-install-note">بستهٔ کامل قلعه‌ها، زمین نقشه در تمام فصل‌ها و تصاویر نهادها، با جزئیات اصلی.</p>
     {pack.manifest&&<div className="web-pack-size">{size(pack.manifest.bytes)} <span>• {pack.total.toLocaleString('fa-IR')} فایل</span></div>}
     {(pack.manifest||checking)&&<><progress max="100" value={percent} aria-label="پیشرفت دانلود فایل‌های بازی"/><div className="web-pack-progress" aria-live="polite"><span>{pack.phase==='ready'?'فایل‌ها آماده‌اند':checking?'در حال بررسی فایل‌ها…':percent.toLocaleString('fa-IR')+'٪'}</span><span>{size(pack.loaded)}</span></div></>}
     {downloading?<button className="btn ghost" type="button" onClick={pauseMapPack}>توقف دانلود</button>:pack.phase==='ready'?<button className="btn ghost" type="button" onClick={inspectMapPack}>بررسی به‌روزرسانی فایل‌ها</button>:<button className="btn web-install-native" type="button" disabled={checking||pack.phase==='unsupported'} onClick={downloadMapPack}>{checking?'در حال آماده‌سازی…':pack.stored?'ادامهٔ دانلود':`دانلود فایل‌ها برای ${platform==='ios'?'آیفون':'اندروید'}`}</button>}
     {pack.error&&<p className="web-pack-error" role="alert">{pack.error}</p>}
     <p className="web-install-note">تا پایان دانلود، برنامه را باز نگه دارید. پس از قطع دانلود، فایل‌های کامل‌شده حفظ می‌شوند. با نسخه‌های جدید فقط فایل‌های تغییرکرده دریافت می‌شوند.</p>
    </div>
    {!installed&&<><h3>۲. افزودن والریا به گوشی</h3>
    {installEvent&&platform==='android'&&<button type="button" className="btn web-install-native" disabled={busy||pack.phase!=='ready'} onClick={install}>نصب روی این دستگاه</button>}
    {platform==='android'?<ol className="web-install-steps"><li>لینک بازی را در Chrome باز کنید و فایل‌ها را دریافت کنید.</li><li>دکمهٔ نصب بالا یا «نصب برنامه» در منوی سه‌نقطهٔ مرورگر را بزنید.</li></ol>:<ol className="web-install-steps"><li>لینک بازی را در Safari باز کنید.</li><li>از منوی اشتراک‌گذاری، «افزودن به صفحهٔ اصلی» را بزنید.</li><li>والریا را با آیکن خودش باز کنید. اگر فایل‌ها آماده نبودند، از «فایل‌های نقشه» داخل برنامه دریافتشان کنید.</li></ol>}</>}
    <p className="web-install-note">برای اطلاعات زنده و انجام کارهای بازی به اینترنت نیاز دارید. پاک‌کردن داده‌های مرورگر یا کمبود شدید فضای گوشی ممکن است دریافت دوبارهٔ فایل‌ها را ضروری کند.</p>
    <button type="button" className="btn ghost" onClick={async()=>{try{await navigator.clipboard.writeText(location.origin+'/?install=1');setMessage('لینک نصب کپی شد؛ می‌توانید آن را برای دوستانتان بفرستید.')}catch{setMessage('آدرس بازی را از نوار مرورگر کپی کنید.')}}}>کپی لینک نصب برای دوستان</button>
    {message&&<p className="web-install-note" role="status">{message}</p>}
   </section>
  </div>,document.body)}
 </>;
}
