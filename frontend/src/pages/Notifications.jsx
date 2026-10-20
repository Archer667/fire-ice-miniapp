import {useEffect,useState} from 'react';
import {api} from '../api.js';
import {useGame} from '../store.jsx';

const TYPES=[['','همهٔ رخدادها'],['war','جنگ و لشکرکشی'],['rebellion','شورش'],['building','ساخت‌وساز'],['trade','تجارت و کاروان'],['diplomacy','پیمان‌ها'],['family','خانواده'],['project','پروژه‌ها'],['institution','نهادها']];
export default function Notifications({goTo}){
  const {toast,refreshUnread}=useGame();
  const [data,setData]=useState(null),[page,setPage]=useState(1),[kind,setKind]=useState(''),[unread,setUnread]=useState(false),[archived,setArchived]=useState(false),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[reload,setReload]=useState(0);
  useEffect(()=>{let active=true;setError('');api.notifications({page,kind,unread,archived,q:search}).then(value=>{if(active)setData(value)}).catch(e=>{if(active)setError(e.message)});const timer=setInterval(()=>{if(!document.hidden)setReload(n=>n+1)},15000);return()=>{active=false;clearInterval(timer)}},[page,kind,unread,archived,search,reload]);
  const action=async(type,ids=[])=>{setBusy(true);try{await api.notificationAction(type,ids);refreshUnread();setReload(n=>n+1)}catch(e){toast(e.message)}finally{setBusy(false)}};
  const filter=setter=>e=>{setter(e.target.value);setPage(1);setData(null)};
  return <><div className="page-title up">صندوق اعلان</div><p className="page-sub">نتیجه‌ها، درخواست‌ها و رخدادهای حساب شما؛ همه در یک صندوق</p>
    <form className="web-notice-filters" onSubmit={e=>{e.preventDefault();setSearch(query.trim());setPage(1);setData(null);setReload(n=>n+1)}}><input aria-label="جست‌وجوی اعلان" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} placeholder="جست‌وجو در اعلان‌ها…"/><button className="btn ghost">جست‌وجو</button><select aria-label="نوع اعلان" value={kind} onChange={filter(setKind)}>{TYPES.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select><button className={`btn ${unread?'':'ghost'}`} type="button" onClick={()=>{setUnread(!unread);setPage(1);setData(null)}}>فقط خوانده‌نشده</button></form>
    <div className="web-notice-filters"><button className="btn ghost" disabled={busy||!data?.unread} onClick={()=>action('read_all')}>خواندن همه ({(data?.unread||0).toLocaleString('fa-IR')})</button><button className="btn ghost" onClick={()=>{setArchived(!archived);setPage(1);setData(null)}}>{archived?'بازگشت به صندوق':'نمایش بایگانی'}</button>{goTo&&<button className="btn ghost" onClick={()=>goTo(4)}>نامه‌های خصوصی و توییت‌ها</button>}</div>
    {error&&<p className="web-error" role="alert">{error}<button className="rbtn" onClick={()=>setReload(n=>n+1)}> تلاش دوباره</button></p>}
    {!data&&!error&&<p className="loading">در حال دریافت اعلان‌ها…</p>}
    {data?.rows.map(row=><article className={`card web-notice ${row.read?'':'unread'}`} key={row.id}><div className="web-notice-head"><strong>{row.read?'خوانده‌شده':'اعلان تازه'}</strong><time>{new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(row.at)?row.at:row.at+'Z').toLocaleString('fa-IR',{timeZone:'Asia/Tehran',dateStyle:'short',timeStyle:'short'})}{row.clock==='game'?' · زمان بازی':''}</time></div><div className="web-notice-body">{row.text}</div>{row.image_url&&<img src={row.image_url} alt="تصویر اعلان" loading="lazy"/>}<div className="web-notice-actions">{!row.read&&<button className="rbtn" disabled={busy} onClick={()=>action('read',[row.id])}>خواندم</button>}<button className="rbtn" disabled={busy} onClick={()=>action(archived?'restore':'archive',[row.id])}>{archived?'بازگرداندن به صندوق':'بایگانی'}</button></div></article>)}
    {data&&!data.rows.length&&<div className="card"><p>اعلانی با این مشخصات وجود ندارد.</p></div>}
    {data&&<div className="grid2"><button className="btn ghost" disabled={page<=1||busy} onClick={()=>{setPage(n=>n-1);setData(null)}}>قبلی</button><button className="btn ghost" disabled={page*30>=data.total||busy} onClick={()=>{setPage(n=>n+1);setData(null)}}>بعدی</button></div>}
  </>;
}
