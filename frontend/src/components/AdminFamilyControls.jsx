import { useEffect, useState } from 'react';
import { api } from '../api.js';
import FamilyIcon from './FamilyIcon.jsx';

const fa = n => Number(n || 0).toLocaleString('fa-IR');

function MarriageControl({ marriage: m, act, busy }) {
  const [penalty,setPenalty]=useState(m.penalty_gold || 1);
  const [reason,setReason]=useState('');
  const [mode,setMode]=useState('penalty');
  const [payer,setPayer]=useState('');
  const [confirm,setConfirm]=useState(false);
  const [dates,setDates]=useState({});
  useEffect(()=>{
    setPenalty(m.penalty_gold || 1);setConfirm(false);setReason('');
    setDates(Object.fromEntries(m.pending_births.map(b=>[b.id,b.at.slice(0,16)])));
  },[m.id,m.admin_revision]);
  const submit=e=>{
    e.preventDefault();
    const body={revision:m.admin_revision||0,reason:reason.trim()};
    act(()=>api.adminMarriageControl(m.id,mode,mode==='penalty'?{...body,penalty_gold:Number(penalty)}:
      mode==='divorce'?{...body,payer_id:payer?Number(payer):null}:
      {...body,births:m.pending_births.map(b=>({child_id:b.id,at:dates[b.id]+(dates[b.id].length===16?':00':'')+'Z'}))}));
  };
  return <details className="card family-admin-record"><summary><FamilyIcon kind="marriage"/><span>{m.parents.map(p=>p.name).join(' و ')}<small>غرامت فعلی: {fa(m.penalty_gold)} طلا · {fa(m.pending_births.length)} تولد باقی‌مانده</small></span></summary>
    <form onSubmit={submit}><label className="f">کنترل ازدواج<select disabled={busy} value={mode} onChange={e=>{setMode(e.target.value);setConfirm(false);}}><option value="penalty">تغییر غرامت</option><option value="divorce">فسخ اجباری ازدواج</option><option value="schedule" disabled={!m.pending_births.length}>زمان‌بندی تولدهای باقی‌مانده</option></select></label>
    {mode==='penalty'&&<><label className="f">غرامت جدید (طلا)<input type="number" required min="1" max="1000000000" step="1" value={penalty} disabled={busy} onChange={e=>setPenalty(e.target.value)}/></label><p className="page-sub">غرامت ازدواج و پیمان وابسته همزمان تغییر می‌کند. اکنون پولی کسر نمی‌شود؛ هر دو طرف از تصمیم ادمین باخبر می‌شوند.</p></>}
    {mode==='divorce'&&<><label className="f">پرداخت غرامت<select disabled={busy} value={payer} onChange={e=>{setPayer(e.target.value);setConfirm(false);}}><option value="">فسخ بدون غرامت</option>{m.parents.map(p=><option key={p.tg_id} value={p.tg_id}>پرداخت {fa(m.penalty_gold)} طلا توسط {p.name}</option>)}</select></label><p className="page-sub">{payer?'مبلغ کامل به همسر دیگر می‌رسد. بدون موجودی کافی، هیچ فسخی انجام نمی‌شود.':'هیچ مبلغی از هیچ‌کدام کسر نمی‌شود.'} پیمان وابسته و تولدهای آینده پایان می‌یابند؛ فرزندان فعلی باقی می‌مانند.</p></>}
    {mode==='schedule'&&<><p className="page-sub">تاریخ‌ها بر اساس ساعت بازی و UTC هستند، نه ساعت محلی گوشی. ترتیب تولدها حفظ شود؛ ادمین می‌تواند از بازهٔ معمول ۲۴ تا ۴۸ ساعت خارج شود.</p>{m.pending_births.map((b,i)=><label className="f" key={b.id}>تولد باقی‌ماندهٔ {fa(i+1)} — UTC<input type="datetime-local" required disabled={busy} value={dates[b.id]||''} onChange={e=>setDates({...dates,[b.id]:e.target.value})}/></label>)}</>}
    <label className="f">دلیل تصمیم مدیریت<textarea required maxLength={500} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)} rows={2}/></label>
    <label className="family-confirm"><input type="checkbox" required disabled={busy} checked={confirm} onChange={e=>setConfirm(e.target.checked)}/>{mode==='divorce'?'فسخ ازدواج و پیمان با شرایط انتخاب‌شده را تأیید می‌کنم.':'اعمال تغییر و اطلاع‌رسانی به طرفین را تأیید می‌کنم.'}</label>
    <button className={`btn ${mode==='divorce'?'ghost':''}`} disabled={busy||!confirm||!reason.trim()}>{busy?'در حال ثبت…':mode==='divorce'?'ثبت فسخ ادمینی':'ثبت تغییرات'}</button></form>
  </details>;
}

function ChildControl({ child:c, act,busy }) {
  const [target,setTarget]=useState(''),[reason,setReason]=useState(''),[confirm,setConfirm]=useState(false);
  const destinations=(c.destinations||[]).filter(p=>p.key!==c.patron_key||p.castle!==c.residence);
  const selected=destinations.find(p=>p.key===target);
  useEffect(()=>{setTarget('');setConfirm(false);setReason('');},[c.id,c.admin_revision,c.patron_key]);
  return <details className="card family-admin-record"><summary><FamilyIcon kind="children"/><span>{c.name}<small>اقامت فعلی: {c.residence}</small></span></summary><form onSubmit={e=>{e.preventDefault();if(selected)act(()=>api.adminMoveChild(c.id,{revision:c.admin_revision||0,expected_patron_key:c.patron_key,parent_key:selected.key,castle:selected.castle,reason:reason.trim()}));}}>
    <label className="f">والد و قلعهٔ اصلی مقصد<select required disabled={busy||!destinations.length} value={target} onChange={e=>{setTarget(e.target.value);setConfirm(false);}}><option value="">انتخاب مقصد</option>{destinations.map(p=><option key={p.key} value={p.key}>{p.name} · {p.castle}</option>)}</select></label>
    {!destinations.length&&<p className="page-sub">والد زندهٔ واجد شرایط دیگری برای انتقال وجود ندارد.</p>}
    <p className="page-sub">با انتقال، هزینه‌های آینده و حق جانشینی فرزند به خاندان مقصد می‌رود. نام، سن و آموزش‌ها حفظ می‌شود؛ هزینه‌های قبلی برنمی‌گردد.</p>
    <label className="f">دلیل جابه‌جایی<textarea required maxLength={500} rows={2} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <label className="family-confirm"><input type="checkbox" required disabled={busy||!selected} checked={confirm} onChange={e=>setConfirm(e.target.checked)}/>تغییر محل اقامت، مسئول هزینه‌ها و خاندان جانشینی را تأیید می‌کنم.</label><button className="btn" disabled={busy||!confirm||!selected||!reason.trim()}>انتقال فرزند</button></form></details>;
}

export default function AdminFamilyControls({data,act,busy}) {
  const [tab,setTab]=useState('marriages'),[query,setQuery]=useState('');
  const rows=(tab==='marriages'?data.active_marriages||[]:data.children||[]).filter(r=>(r.name||r.parents?.map(p=>p.name).join(' ')||'').includes(query.trim()));
  return <section className="family-admin-controls"><h2 className="sect">مدیریت خانواده‌های فعال</h2><div className="family-tabs" role="tablist" aria-label="مدیریت خانواده"><button type="button" role="tab" aria-selected={tab==='marriages'} className={tab==='marriages'?'on':''} onClick={()=>{setTab('marriages');setQuery('');}}>ازدواج‌ها</button><button type="button" role="tab" aria-selected={tab==='children'} className={tab==='children'?'on':''} onClick={()=>{setTab('children');setQuery('');}}>جابه‌جایی فرزندان</button></div><label className="f">جست‌وجوی نام<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="نام همسر یا فرزند"/></label>{!rows.length&&<p className="page-sub">موردی برای نمایش نیست.</p>}{rows.map(r=>tab==='marriages'?<MarriageControl key={r.id} marriage={r} act={act} busy={busy}/>:<ChildControl key={r.id} child={r} act={act} busy={busy}/>)}</section>;
}
