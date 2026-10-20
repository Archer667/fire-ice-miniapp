import {useState} from 'react';
import {req} from '../api.js';
import {REGIONS_STATIC} from '../gamedata.js';
export default function CharacterAdmission({player,onApproved,toast}) {
 const [options,setOptions]=useState(null),[region,setRegion]=useState(player.requested_region||Object.keys(REGIONS_STATIC)[0]),[place,setPlace]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const load=()=>req('/api/admin/character-admission/options').then(setOptions).catch(e=>setError(e.message));
 const submit=async e=>{e.preventDefault();setBusy(true);setError('');try{await req(`/api/admin/players/${player.tg_id}/approve-character`,{method:'POST',body:JSON.stringify({region,place,character_key:player.character_key||''})});toast('کاراکتر بدون مالکیت قلعه تأیید شد');onApproved();}catch(e){setError(e.message);}finally{setBusy(false);}};
 return <details className="character-admission" onToggle={e=>{if(e.currentTarget.open&&!options&&!busy)load();}}><summary>تأیید به‌عنوان کاراکتر بدون قلعه</summary><p className="page-sub">محل حضور کاراکتر تعیین می‌شود؛ مالکیت و مدیریت قلعهٔ میزبان واگذار نمی‌شود.</p><form onSubmit={submit}>
 <label className="f">اقلیم کاراکتر<select value={region} onChange={e=>setRegion(e.target.value)} disabled={busy}>{Object.entries(REGIONS_STATIC).map(([id,row])=><option key={id} value={id}>{row.name}</option>)}</select></label>
 <label className="f">محل اقامت اولیه<select required value={place} onChange={e=>setPlace(e.target.value)} disabled={busy||!options}><option value="">انتخاب قلعه، شهر یا مقر نهاد…</option>{options?.places.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
 {error&&<p role="alert" className="page-sub">{error}</p>}{!options&&<button className="btn ghost" type="button" onClick={load}>دریافت مکان‌ها</button>}
 <button className="btn" disabled={busy||!place}>{busy?'در حال تأیید…':'تأیید کاراکتر بدون قلعه'}</button>
 </form></details>;
}
