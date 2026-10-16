import {useEffect,useState} from 'react';
import {req} from '../api.js';
import {useGame} from '../store.jsx';
import '../styles/character-travel.css';

export const travelStatus={pending:'منتظر پذیرش',travelling:'در راه',arrived:'رسیده',rejected:'پذیرفته نشد',redirected:'مسیر تغییر کرد',superseded:'جایگزین شد',held:'متوقف توسط ادمین',cancelled:'لغو شده'};
export default function CharacterTravel({guestsOnly=false}){
 const {toast}=useGame();const [data,setData]=useState(null),[error,setError]=useState(''),[target,setTarget]=useState(''),[children,setChildren]=useState([]),[busy,setBusy]=useState(false),[section,setSection]=useState('journey');
 const refresh=()=>req('/api/character-travel').then(v=>{setData(v);setError('');}).catch(e=>setError(e.message));
 useEffect(()=>{refresh();const timer=setInterval(refresh,30000);return()=>clearInterval(timer);},[]);
 useEffect(()=>{const trip=data?.requests.find(r=>r.id===data.state.trip);if(trip)setChildren(trip.children);},[data?.state.trip]);
 const act=async(path,body)=>{if(busy)return;setBusy(true);try{const result=await req('/api/character-travel/'+path,{method:'POST',body:JSON.stringify(body)});toast(result.message||'ثبت شد');await refresh();}catch(e){toast(e.message);}finally{setBusy(false);}};
 if(error)return <div className="card travel-panel" role="alert">{error}<button className="btn ghost" onClick={refresh}>تلاش دوباره</button></div>;
 if(!data)return <div className="card travel-panel">در حال دریافت وضعیت کاراکتر…</div>;
 const state=data.state, own=data.requests.filter(r=>r.character===state.id),incoming=data.requests.filter(r=>r.character!==state.id&&['pending','travelling','held'].includes(r.status));
 const trip=own.find(r=>r.id===state.trip);
 const guests=<><h3>مهمانان و درخواست‌های ورود</h3><p className="travel-muted">پذیرش فقط برای میزبان‌های مقصد نمایش داده می‌شود.</p>
 {incoming.length===0&&<p>درخواست ورود تازه‌ای ثبت نشده است.</p>}{incoming.map(r=><article className="travel-row" key={r.id}><strong>{r.name}</strong><span>{r.target} · {r.children.length+1} نفر</span><div className="travel-actions">{r.status!=='pending'?<span className="travel-chip">{travelStatus[r.status]}</span>:<><button disabled={busy||data.paused} className="btn" onClick={()=>act('respond',{id:r.id,accept:true})}>پذیرش ورود</button><button disabled={busy||data.paused} className="btn ghost" onClick={()=>act('respond',{id:r.id,accept:false})}>رد درخواست</button></>}</div></article>)}
 {data.guests.map(g=><details className="travel-row" key={g.id}><summary><strong>{g.name}</strong><span>{g.place} · {g.captive?'اسیر':'مهمان'}</span></summary><div className="travel-actions">
 {g.captive?<button className="btn" disabled={busy||data.paused} onClick={()=>act('release',{subject:g.id})}>آزادسازی</button>:<><button className="btn ghost" disabled={busy||data.paused} onClick={()=>{const reason=window.prompt('دلیل درخواست اسارت برای بررسی ادمین');if(reason?.trim())act('capture',{subject:g.id,reason});}}>درخواست اسارت</button>{g.tg_id&&<button className="btn ghost" disabled={busy||data.paused} onClick={()=>{if(window.confirm('درخواست بازگشت مهمان به مبدأ ثبت شود؟'))act('expel',{subject:g.id});}}>اخراج</button>}</>}
 </div></details>)}</>;
 if(guestsOnly)return <section className="card travel-panel" dir="rtl">{guests}</section>;
 return <section className="travel-panel" dir="rtl"><header className="travel-hero"><span className="travel-eyebrow">سفرنامهٔ خاندان</span><h1>کاراکتر و سفر</h1><p>{state.name} · {state.captive?'در اسارت':trip?'در مسیر '+trip.target:state.place||'در انتظار تعیین محل توسط ادمین'}</p><span className="travel-chip">{data.free_travel?'سفر رایگان برای کاراکتر بدون قلعه':'۱۰ شراب برای هر مسافر'}</span></header>
 <nav className="travel-tabs"><button className={'btn '+(section==='journey'?'':'ghost')} onClick={()=>setSection('journey')}>حضور و سفر</button><button className={'btn '+(section==='guests'?'':'ghost')} onClick={()=>setSection('guests')}>مهمانان {incoming.length>0&&`(${incoming.length})`}</button></nav>
 {section==='guests'?<div className="card">{guests}</div>:<>
 {state.captive&&<div className="card">در وضعیت اسارت، سفر تا زمان آزادسازی غیرفعال است.</div>}
 {trip&&<div className="card"><strong>{travelStatus[trip.status]}</strong><p>{trip.origin} ← {trip.target}</p><p>زمان باقی‌مانده: {Math.max(0,Math.ceil((new Date(trip.arrival_at+'Z')-new Date(data.game_now+'Z'))/60000)).toLocaleString('fa-IR')} دقیقهٔ بازی</p></div>}
 <form className="card" onSubmit={e=>{e.preventDefault();act('requests',{target,children,request_id:crypto.randomUUID()});}}><h3>{trip?'انتخاب مقصد تازه':'آغاز سفر'}</h3><label className="f">مقصد<select required value={target} onChange={e=>setTarget(e.target.value)}><option value="">قلعه، شهر یا مقر نهاد…</option>{data.destinations.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
 <fieldset><legend>فرزندان همراه</legend>{data.children.length===0?<p className="travel-muted">فرزندی برای همراهی ثبت نشده است.</p>:data.children.map(c=><label className="travel-child" key={c.id}><input type="checkbox" disabled={!c.available||busy} checked={children.includes(c.child_id)} onChange={e=>setChildren(old=>e.target.checked?[...old,c.child_id]:old.filter(id=>id!==c.child_id))}/><span>{c.name}<small>{c.captive?'در اسارت':c.place||'در سفر'}{!c.available?' · امکان همراهی ندارد':''}</small></span></label>)}</fieldset>
 <p className="travel-muted">برای مقصدهای دارای میزبان، سفر پس از پذیرش آغاز می‌شود. سفر همسر از حساب کاراکتر او ثبت می‌شود.</p><button className="btn" disabled={busy||data.paused||!!state.captive||!target}>ثبت درخواست · {data.free_travel?'رایگان':`${10*(children.length+1)} شراب`}</button></form>
 <div className="card"><h3>درخواست‌ها و سفرهای من</h3>{own.length===0?<p>هنوز سفری ثبت نشده است.</p>:own.map(r=><details className="travel-row" key={r.id}><summary><strong>{r.target}</strong><span>{travelStatus[r.status]}</span></summary><p>{r.origin} ← {r.target}</p><p>{r.children.length+1} مسافر · {r.cost??(data.free_travel?0:10*(r.children.length+1))} شراب</p></details>)}</div></>}
 </section>;
}
