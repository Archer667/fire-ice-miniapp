import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';

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
  <button ref={trigger} type="button" className={header?'rbtn web-install-trigger':'btn ghost web-install-login'} onClick={()=>setOpen(true)}>{installed?'راهنمای برنامه':'نصب برنامه'}</button>
  {open&&createPortal(<div className="web-modal web-install-overlay" onClick={e=>{if(e.target===e.currentTarget)setOpen(false)}}>
   <section ref={dialog} className="card web-install-card" role="dialog" aria-modal="true" aria-labelledby="install-title" dir="rtl">
    <button type="button" className="rbtn web-install-close" aria-label="بستن راهنمای نصب" onClick={()=>setOpen(false)}>×</button>
    <img className="web-install-icon" src="/pwa/valyria-icon-192.png" alt="نشان والریا" width="88" height="88"/>
    <span className="web-install-eyebrow">والریا همیشه همراه شما</span>
    <h2 id="install-title" dir="ltr">Valyria Web App</h2>
    <p className="page-sub">والریا را به صفحهٔ اصلی گوشی اضافه کنید و با آیکن برنامه وارد بازی شوید.</p>
    <div className="grid2 web-install-tabs" role="group" aria-label="نوع گوشی">
     <button type="button" className={'btn '+(platform==='android'?'':'ghost')} aria-pressed={platform==='android'} onClick={()=>setPlatform('android')}>اندروید</button>
     <button type="button" className={'btn '+(platform==='ios'?'':'ghost')} aria-pressed={platform==='ios'} onClick={()=>setPlatform('ios')}>آیفون و آیپد</button>
    </div>
    {!installed&&<><h3>افزودن والریا به گوشی</h3>
    {installEvent&&platform==='android'&&<button type="button" className="btn web-install-native" disabled={busy} onClick={install}>نصب روی این دستگاه</button>}
    {platform==='android'?<ol className="web-install-steps"><li>لینک بازی را در Chrome باز کنید.</li><li>دکمهٔ نصب بالا یا «نصب برنامه» در منوی سه‌نقطهٔ مرورگر را بزنید.</li></ol>:<ol className="web-install-steps"><li>لینک بازی را در Safari باز کنید.</li><li>از منوی اشتراک‌گذاری، «افزودن به صفحهٔ اصلی» را بزنید.</li><li>والریا را با آیکن خودش باز کنید.</li></ol>}</>}
    <p className="web-install-note">برای ورود و انجام کارهای بازی به اینترنت نیاز دارید. تصاویر و مدل‌ها هنگام نیاز بارگذاری می‌شوند.</p>
    <button type="button" className="btn ghost" onClick={async()=>{try{await navigator.clipboard.writeText(location.origin+'/?install=1');setMessage('لینک نصب کپی شد؛ می‌توانید آن را برای دوستانتان بفرستید.')}catch{setMessage('آدرس بازی را از نوار مرورگر کپی کنید.')}}}>کپی لینک نصب برای دوستان</button>
    {message&&<p className="web-install-note" role="status">{message}</p>}
   </section>
  </div>,document.body)}
 </>;
}
