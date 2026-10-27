import {useEffect, useState} from 'react';
import {api} from '../api.js';
import {useGame} from '../store.jsx';

const fa = value => Number(value || 0).toLocaleString('fa-IR');
const eventLabels = {popularity:'محبوبیت', influence:'نفوذ', pact:'پیمان', pact_exit:'پیمان', proposal:'شورا', proposal_result:'شورا', tribute:'خراج'};

export default function RealmCouncil(){
  const {toast}=useGame();
  const [overview,setOverview]=useState(null);
  const [proposals,setProposals]=useState(null);
  const [events,setEvents]=useState(null);
  const [busy,setBusy]=useState('');
  const [draft,setDraft]=useState({title:'',description:'',scope:'realm',options:['موافقم','مخالفم']});
  const load=()=>Promise.all([
    api.realmOverview().then(setOverview), api.realmProposals().then(setProposals), api.realmEvents().then(setEvents),
  ]).catch(e=>toast(e.message));
  useEffect(()=>{load();},[]);
  const changeOption=(index,value)=>setDraft(d=>({...d,options:d.options.map((x,i)=>i===index?value:x)}));
  const create=async()=>{
    setBusy('create');
    try{await api.realmCreateProposal(draft);toast('پیشنهاد در شورا ثبت شد');setDraft({title:'',description:'',scope:'realm',options:['موافقم','مخالفم']});await load();}
    catch(e){toast(e.message);}finally{setBusy('');}
  };
  const support=async id=>{setBusy('support:'+id);try{await api.realmSupportProposal(id);toast('حمایتت ثبت شد');await load();}catch(e){toast(e.message);}finally{setBusy('');}};
  const vote=async(id,option)=>{setBusy('vote:'+id);try{await api.realmVoteProposal(id,option);toast('رأیت ثبت شد');await load();}catch(e){toast(e.message);}finally{setBusy('');}};
  if(!overview||!proposals||!events)return <div className="card realm-loading">در حال دریافت وضعیت قلمرو…</div>;
  return <section className="realm-council">
    <div className="realm-metrics">
      <article><small>محبوبیت مردم</small><strong>{fa(overview.popularity)}</strong><span>{overview.popularity_band.label}</span></article>
      <article><small>نفوذ سیاسی</small><strong>{fa(overview.influence)}</strong><span>قابل خرج در شورا</span></article>
      <article><small>رونق قلمرو</small><strong>{fa(overview.prosperity.score)}</strong><span>{overview.prosperity.label}</span></article>
      <article><small>بازده مالیات</small><strong>{fa(overview.popularity_effects.tax_yield_percent)}٪</strong><span>با محبوبیت فعلی</span></article>
    </div>
    <div className="realm-columns">
      <div>
        <div className="sect">پیشنهادهای شورا</div>
        {!proposals.length&&<div className="card realm-empty">هنوز پیشنهادی در شورا ثبت نشده است.</div>}
        {proposals.map(p=><article className={`card realm-proposal ${p.status}`} key={p.id}>
          <header><div><b>{p.title}</b><small>{p.author_name} · {p.scope==='region'?'اقلیمی':'سراسری'}</small></div><span>{p.status==='open'?'در حال رأی‌گیری':p.status==='enacted'?'تصویب‌شده':'پایان‌یافته'}</span></header>
          <p>{p.description}</p>
          <div className="realm-support"><span>{fa(p.supporters)} حامی · {fa(p.total_votes)} رأی</span>{p.status==='open'&&!p.supported&&<button className="btn ghost" disabled={!!busy} onClick={()=>support(p.id)}>حمایت با {fa(overview.rules.support_cost)} نفوذ</button>}</div>
          <div className="realm-ballot">{p.options.map((option,index)=>{const total=Math.max(1,p.total_votes);const pct=Math.round((p.tally[index]||0)*100/total);return <button type="button" key={index} disabled={p.status!=='open'||!!busy} className={p.my_vote===index?'chosen':''} onClick={()=>vote(p.id,index)}><i style={{width:pct+'%'}}/><span>{option}</span><em>{fa(p.tally[index])} · {fa(pct)}٪</em></button>;})}</div>
          {p.outcome&&<div className="realm-outcome">نتیجه: {p.outcome}</div>}
        </article>)}
      </div>
      <aside>
        <details className="card realm-compose"><summary>ثبت پیشنهاد تازه</summary>
          <label className="f">عنوان</label><input maxLength={100} value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/>
          <label className="f">شرح پیشنهاد</label><textarea maxLength={2500} rows={5} value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})}/>
          <label className="f">محدوده</label><select value={draft.scope} onChange={e=>setDraft({...draft,scope:e.target.value})}><option value="realm">تمام قلمرو</option><option value="region">اقلیم خودم</option></select>
          <label className="f">گزینه‌ها</label>{draft.options.map((option,index)=><div className="realm-option-edit" key={index}><input maxLength={80} value={option} onChange={e=>changeOption(index,e.target.value)}/>{draft.options.length>2&&<button type="button" onClick={()=>setDraft(d=>({...d,options:d.options.filter((_,i)=>i!==index)}))}>×</button>}</div>)}
          {draft.options.length<5&&<button type="button" className="btn ghost" onClick={()=>setDraft(d=>({...d,options:[...d.options,'']}))}>افزودن گزینه</button>}
          <p className="page-sub">ثبت پیشنهاد {fa(overview.rules.proposal_cost)} نفوذ مصرف می‌کند. رأی اول هر پرونده یک نفوذ برمی‌گرداند.</p>
          <button className="btn" disabled={!!busy} onClick={create}>{busy==='create'?'در حال ثبت…':'ثبت در شورا'}</button>
        </details>
        <div className="card realm-ledger"><h3>رویدادهای اثرگذار</h3>{events.slice(0,12).map(e=><div key={e.id}><span>{eventLabels[e.kind]||'قلمرو'}</span><p><b>{e.title}</b>{e.detail&&<small>{e.detail}</small>}</p></div>)}</div>
        {!!overview.relations.length&&<div className="card realm-relations"><h3>اعتبار میان خاندان‌ها</h3>{overview.relations.slice(0,8).map(r=><div key={r.tg_id}><span>{r.name}</span><b className={r.score<0?'negative':''}>{r.score>0?'+':''}{fa(r.score)}</b></div>)}</div>}
      </aside>
    </div>
  </section>;
}
