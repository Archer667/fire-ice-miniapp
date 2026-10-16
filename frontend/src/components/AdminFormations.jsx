import {useEffect,useState} from 'react';
import {req} from '../api.js';
import CastlePicker from './CastlePicker.jsx';
import '../styles/admin-tools.css';
export default function AdminFormations({leaderId=null,toast,onChanged=()=>{},canManage=true,query=''}){
 const [expanded,setExpanded]=useState({}),[rows,setRows]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[dest,setDest]=useState({}),[confirmed,setConfirmed]=useState({});
 const load=()=>req('/api/admin/army-groups'+(leaderId?`?leader_id=${leaderId}`:'')).then(v=>setRows(Array.isArray(v)?v:[])).catch(e=>setError(e.message));
 useEffect(()=>{setRows(null);load();},[leaderId]);
 const act=async(g,action,memberId='')=>{
  if(['destroy','disband','split','detach'].includes(action)&&!window.confirm({destroy:'تمام اعضای این لشکر مشترک بدون بازپرداخت منهدم شوند؟',disband:'تمام لشکرهای عضو منحل و هزینهٔ باقی‌ماندهٔ هر لشکر به صاحب آن برگردد؟',split:'اشتراک لغو شود؟ هر لشکر مستقل در محل فعلی باقی می‌ماند.',detach:'این عضو مستقل شود؟ محل و نیروهایش حفظ می‌شوند.'}[action]))return;
  setBusy(true);try{await req(`/api/admin/army-groups/${g.id}`,{method:'POST',body:JSON.stringify({action,destination:dest[g.id]?.[0]||'',member_id:memberId,confirm_battle_exit:!!confirmed[g.id]})});toast('عملیات ثبت شد');await load();onChanged();}catch(e){toast(e.message);}finally{setBusy(false);}
 };
 if(error)return <div className="card">{error}<button className="btn ghost" onClick={()=>{setError('');load();}}>تلاش دوباره</button></div>;
 if(rows===null)return <div className="page-sub">در حال دریافت لشکرهای مشترک…</div>;
 const filtered=rows.filter(g=>`${g.name} ${g.leader_name} ${g.location} ${g.members.map(m=>m.name+' '+m.player).join(' ')}`.toLowerCase().includes(query.toLowerCase()));
 return <section className="admin-tools"><div className="sect">لشکرهای مشترک{leaderId?' تحت فرمان بازیکن':''}</div>{!filtered.length&&<div className="card page-sub">لشکر مشترکی در این فهرست وجود ندارد.</div>}{filtered.map(g=><details className="card admin-tool-dossier" key={g.id} onToggle={e=>{const open=e.currentTarget.open;setExpanded(o=>({...o,[g.id]:open}));}}><summary><strong>{g.name}</strong><span>فرمانده: {g.leader_name} · {g.members.length.toLocaleString('fa-IR')} لشکر</span></summary>{expanded[g.id]&&<><p>{g.location} · {g.in_battle?'درگیر نبرد':'آزاد'}</p><p>{[...g.forces,...g.ships,...g.devices].map(t=>`${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ')}</p>
 {g.members.map(m=><article className="admin-tool-member" key={m.id}><b>{m.player} · {m.name}</b><p>{m.men.toLocaleString('fa-IR')} نیرو · {m.location}</p>{canManage&&<button className="btn ghost" disabled={busy} onClick={()=>act(g,'detach',m.id)}>جداکردن این لشکر</button>}</article>)}
 {canManage&&<><label className="f">مقصد انتقال تمام اعضا</label><CastlePicker value={dest[g.id]||[]} onChange={v=>setDest(o=>({...o,[g.id]:v}))} max={1} allowOccupied/>{g.in_battle&&<label className="family-confirm"><input type="checkbox" checked={!!confirmed[g.id]} onChange={e=>setConfirmed(o=>({...o,[g.id]:e.target.checked}))}/>خروج تمام اعضا از نبرد تأیید می‌شود.</label>}<div className="admin-tool-actions"><button className="btn" disabled={busy||!dest[g.id]?.length||(g.in_battle&&!confirmed[g.id])} onClick={()=>act(g,'relocate')}>انتقال فوری گروه</button><button className="btn ghost" disabled={busy} onClick={()=>act(g,'split')}>لغو اشتراک</button><button className="btn ghost" disabled={busy||(g.in_battle&&!confirmed[g.id])} onClick={()=>act(g,'disband')}>انحلال همهٔ اعضا</button><button className="btn ghost danger" disabled={busy||(g.in_battle&&!confirmed[g.id])} onClick={()=>act(g,'destroy')}>انهدام همهٔ اعضا</button></div></>}
 </>}</details>)}</section>;
}
