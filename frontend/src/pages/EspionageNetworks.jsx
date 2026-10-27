import {useEffect,useState} from 'react';
import {api} from '../api.js';
import {useGame} from '../store.jsx';
import LimitedText from '../components/LimitedText.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import {castleLabel,spyTravelMinutes} from '../gamedata.js';
import {SpyStatus,SpyEmpty,useSpyCommand,fa,spyDate} from '../components/EspionageShared.jsx';

export default function EspionageNetworks(){
  const {me,setMe,toast}=useGame();
  const [tab,setTab]=useState('networks');
  const [meta,setMeta]=useState(null),[rows,setRows]=useState([]),[questions,setQuestions]=useState([]);
  const [map,setMap]=useState(null),[target,setTarget]=useState(null),[scenario,setScenario]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const command=useSpyCommand();
  async function load(){try{const [m,n,q]=await Promise.all([api.spy('/meta'),api.spy('/mine'),api.spy('/questions')]);setMeta(m);setRows(n);setQuestions(q);setError('');}catch(e){setError(e.message);}}
  useEffect(()=>{load();},[]);
  useEffect(()=>{if(tab==='deploy'&&!map)api.map().then(setMap).catch(e=>setError(e.message));},[tab]);
  async function run(path,data,done){setBusy(true);try{await command(path,data);done?.();toast('ثبت شد');await load();}catch(e){toast(e.message);}finally{setBusy(false);}}
  return <div className="spy-page">
    <div className="spy-head"><div className="spy-mark">◉</div><div><div className="page-title">جاسوسی</div><div className="page-sub">شبکه‌های پنهان و گزارش‌های محرمانه</div></div></div>
    {error&&<div className="spy-note" role="alert">{error}<button className="btn ghost" onClick={load}>تلاش دوباره</button></div>}
    {meta&&<div className="spy-stats"><div><b>{fa(meta.networks_used)} / {fa(meta.max_networks)}</b><small>شبکه‌های باز</small></div><div><b>{fa(meta.weekly_questions)}</b><small>سؤال هر شبکه در ۷ روز بازی</small></div><div><b>{fa(meta.gold_cost)}</b><small>طلای استقرار</small></div></div>}
    <nav className="spy-tabs" aria-label="بخش‌های جاسوسی">{[['networks','شبکه‌ها'],['questions','سؤال‌ها و پاسخ‌ها'],['deploy','استقرار تازه']].map(([k,t])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{t}</button>)}</nav>
    {tab==='networks'&&<><div className="spy-note">پس از رسیدن به مقصد و داوری رول، شانس استقرار امتحان می‌شود. هر شبکهٔ موفق سهمیهٔ مستقل دارد و تا جمع‌کردن یا بسته‌شدن فعال می‌ماند. پاسخ‌ها از مسیر همان شبکه می‌رسند؛ قطع ارتباط ممکن است پرونده را به بررسی خطر ببرد.</div>
      {!rows.length&&<SpyEmpty>{meta?'هنوز شبکه‌ای نداری. از «استقرار تازه» شروع کن.':'در حال دریافت پرونده‌ها…'}</SpyEmpty>}
      {rows.map(n=><details className="card spy-dossier" key={n.id}><summary><div><b>{castleLabel(n.target)}</b><small>{spyDate(n.created_at)} · {n.arrived?'رسیده به مقصد':'در مسیر'}</small></div><SpyStatus status={n.status}/></summary><div className="spy-content">
        <div className="spy-meta"><span>مبدأ: {castleLabel(n.origin)}</span><span>زمان رسیدن: {spyDate(n.arrival_at)}</span>{n.quota&&<span>سؤال‌های این هفته: {fa(n.quota.used)} / {fa(n.quota.limit)}</span>}</div>
        {n.blocked_reason&&<div className="spy-note">{n.blocked_reason}</div>}{n.note&&<div className="spy-note">{n.note}</div>}
        <details><summary>رول استقرار</summary><p className="spy-prose">{n.scenario}</p></details>
        {n.status==='active'&&meta?.enabled&&<QuestionForm busy={busy} remaining={n.quota?.remaining} onSend={(text,done)=>run(`/networks/${n.id}/questions`,{text},done)}/>}
        {['pending','active','suspended'].includes(n.stored_status)&&<div className="spy-actions"><button className="btn ghost" disabled={busy} onClick={()=>{if(confirm('شبکه جمع شود؟ سؤال‌های بی‌پاسخ آن بسته می‌شوند و هزینهٔ استقرار برنمی‌گردد.'))run(`/networks/${n.id}/recall`);}}>جمع‌کردن شبکه</button></div>}
      </div></details>)}
    </>}
    {tab==='questions'&&<>{!questions.length&&<SpyEmpty>سؤالی ثبت نشده است.</SpyEmpty>}{questions.map(q=><details key={q.id} className="card spy-dossier"><summary><div><b>{castleLabel(q.target)}</b><small>{spyDate(q.created_at)}</small></div><SpyStatus status={q.status}/></summary><div className="spy-content"><p className="spy-prose">{q.text}</p>{q.review_note&&<div className="spy-note">{q.review_note}</div>}{q.answer&&<div className="spy-note spy-answer spy-prose">{q.answer}</div>}{q.status==='returned'&&<QuestionForm busy={busy} initial={q.text} editing onSend={(text,done)=>run(`/questions/${q.id}/edit`,{text},done)}/>}</div></details>)}</>}
    {tab==='deploy'&&<><div className="spy-note">قلعهٔ هدف و روش نفوذ را مشخص کن. هزینه هنگام ثبت درخواست پرداخت می‌شود؛ تعداد و نقش جاسوس‌ها را در رول بنویس. در هر قلعه فقط یک شبکهٔ باز می‌توانی داشته باشی.</div>
      {!meta?.can_deploy?<SpyEmpty>برای استقرار تازه به قلعهٔ مبدأ نیاز داری. شبکه‌های قبلی از بخش «شبکه‌ها» قابل پیگیری‌اند.</SpyEmpty>:!meta.enabled?<SpyEmpty>ثبت درخواست تازه فعلاً بسته است.</SpyEmpty>:<>
        {map?<WesterosMap data={map} meCastles={[me.castle,...(me.castles||[])]} pickLabel="انتخاب هدف جاسوسی" onSelectTarget={setTarget}/>:<SpyEmpty>در حال دریافت نقشه…</SpyEmpty>}
        <div className="card"><label className="f">قلعهٔ هدف</label><div className="spy-note">{target?`${castleLabel(target.name)} · حدود ${fa(spyTravelMinutes(me.castle,target.name))} دقیقه سفر`:'یک قلعه را روی نقشه انتخاب کن.'}</div><label className="f">رول استقرار</label><LimitedText limitKind="scenario_words" value={scenario} onChange={e=>setScenario(e.target.value)} placeholder="روش نفوذ، پوشش و ارتباط جاسوس‌ها را بنویس…"/><div className="spy-actions"><button className="btn" disabled={busy||!target?.owner||target?.mine||scenario.trim().length<10||meta.networks_used>=meta.max_networks||Number(me.resources?.gold||0)<meta.gold_cost} onClick={()=>run('/send',{target_castle:target.name,scenario},()=>{setScenario('');setTarget(null);setTab('networks');api.me().then(setMe).catch(()=>{});})}>{busy?'در حال ثبت…':`ثبت استقرار · ${fa(meta.gold_cost)} طلا`}</button></div></div>
      </>}
    </>}
  </div>;
}
function QuestionForm({onSend,busy,remaining,initial='',editing=false}){
  const [text,setText]=useState(initial);
  return <div><label className="f">{editing?'اصلاح سؤال':'سؤال از شبکه'}</label><LimitedText limitKind="request_words" value={text} onChange={e=>setText(e.target.value)} placeholder="دقیقاً چه اطلاعاتی می‌خواهی؟"/>{!editing&&<div className="spy-meta">هر سؤالِ ثبت‌شده یک سهمیه مصرف می‌کند. فقط سؤال ردشده سهمیه را برمی‌گرداند.</div>}<div className="spy-actions"><button className="btn" disabled={busy||text.trim().length<3||(!editing&&!remaining)} onClick={()=>onSend(text,()=>setText(''))}>{editing?'ارسال اصلاحیه':remaining?'ثبت سؤال':'سهمیه تمام شده'}</button></div></div>;
}
