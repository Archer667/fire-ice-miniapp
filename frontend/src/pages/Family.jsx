import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { gameNow } from '../gameClock.js';
import FamilyIcon from '../components/FamilyIcon.jsx';
import '../family.css';

const fa = n => Number(n || 0).toLocaleString('fa-IR');
const time = v => Date.parse(v?.endsWith?.('Z') ? v : v + 'Z');
const remaining = v => { const h = Math.max(0, Math.ceil((time(v) - gameNow()) / 3600000)); return h ? `${fa(h)} ساعت بازی` : 'آماده'; };
const labels = {proposed:'منتظر پاسخ', accepted:'منتظر تأیید مدیریت', active:'پیوند برقرار', rejected:'رد شده', expired:'مهلت تمام شده', ended:'پایان‌یافته'};
const skills = {strategy:'راهبرد', diplomacy:'دیپلماسی', economy:'اقتصاد'};
const costs = c => `${fa(c?.gold)} طلا · ${fa(c?.food)} غذا`;

function ChildCard({ child: c, ownKey, stages, act, busy, admin = false }) {
  const [name, setName] = useState(c.named ? c.name : '');
  const [specialty, setSpecialty] = useState('strategy');
  useEffect(() => setName(c.named ? c.name : ''), [c.name, c.named]);
  const adult = time(c.adult_at) <= gameNow();
  const day = Math.max(0, Math.min(3, Math.floor((gameNow() - time(c.born_at)) / 86400000)));
  const own = ownKey === c.patron_key;
  const alive = c.status === 'alive';
  const editable = alive && (admin || own && (!adult || !c.named));
  return <article className="card family-child">
    <div className="family-heading"><FamilyIcon kind={adult ? 'heir' : 'children'} /><div><h3 className="sect">{c.name}</h3><p className="page-sub">{c.gender === 'lady' ? 'دختر' : 'پسر'} · {c.status === 'succeeded' ? 'کاراکتر فعلی' : !alive ? 'از چرخهٔ جانشینی خارج شده' : adult ? 'بالغ' : `روز ${fa(day + 1)} رشد`}</p></div><span className="family-tag">{own ? 'مسئولیت تو' : 'خاندان دیگر'}</span></div>
    <dl className="family-facts"><div><dt>اقامت</dt><dd>{c.residence}</dd></div><div><dt>والدین</dt><dd>{c.parents.map(p => p.name).join(' و ')}</dd></div>{alive && !adult && <div><dt>تا بلوغ</dt><dd>{remaining(c.adult_at)}</dd></div>}</dl>
    {editable && <form className="family-name" onSubmit={e => {e.preventDefault(); act(() => admin ? api.adminFamilyName(c.id, name.trim()) : api.familyChild(c.id, {name: name.trim()}));}}><label className="f">نام فرزند<input aria-label={`نام ${c.name}`} value={name} required minLength={2} maxLength={40} onChange={e => setName(e.target.value)} placeholder="نام را تو انتخاب می‌کنی" disabled={busy} /></label><button className="btn ghost" disabled={busy || name.trim().length < 2}>ثبت نام</button></form>}
    {alive && <><div className="family-stages" aria-label="چهار روز آموزش">{stages.map((label, i) => <div key={label} className={c.training?.[i] ? 'done' : !adult && i === day ? 'current' : ''}><span>{fa(i + 1)}</span><small>{label}</small><small>{c.training?.[i] ? 'انجام شد' : adult || i < day ? 'انجام نشد' : i === day ? 'نوبت امروز' : 'در آینده'}</small></div>)}</div>
    {own && !adult && !c.training?.[day] && <form onSubmit={e => {e.preventDefault(); act(() => api.familyChild(c.id, {stage: day, specialty}));}}><p className="page-sub">هزینهٔ این مرحله فقط از تو: {costs(c.training_cost)}</p><div className="family-name"><label className="f">مسیر آموزش<select value={specialty} disabled={busy} onChange={e => setSpecialty(e.target.value)}>{Object.entries(skills).map(([v,t]) => <option key={v} value={v}>{t}</option>)}</select></label><button className="btn" disabled={busy}>انجام آموزش</button></div></form>}
    {Object.keys(c.training || {}).length > 0 && <p className="page-sub">آموزش‌های ثبت‌شده: {Object.values(c.training).map(t => skills[t.specialty]).join(' · ')}</p>}</>}
  </article>;
}

export function FamilySummary({ goTo }) {
  const [data, setData] = useState(null);
  useEffect(() => {let live = true; api.family().then(d => live && setData(d)).catch(() => {});return () => {live = false;};}, []);
  if (!data) return null;
  const m = data.marriages.find(m => m.status === 'active');
  const partner = m?.parents.find(p => p.key !== data.character_key);
  const tasks = data.children.filter(c => c.patron_key === data.character_key && c.status === 'alive' && (!c.named || time(c.adult_at) > gameNow() && !c.training?.[Math.floor((gameNow()-time(c.born_at))/86400000)])).length;
  return <button className="card family-summary" onClick={() => goTo(11)}><FamilyIcon /><span><strong>خاندان و خانواده</strong><small>{partner ? `همسر: ${partner.name}` : 'پیوند و پرورش نسل آینده'} · {data.succession.heir ? `وارث: ${data.succession.heir.name}` : 'هنوز وارث بالغ نداری'}</small></span><span className="family-tag">{tasks ? `${fa(tasks)} کار منتظر` : 'مشاهده'}</span></button>;
}

export default function Family() {
  const { toast, setMe } = useGame();
  const [data, setData] = useState(null), [tab, setTab] = useState('marriage'), [busy, setBusy] = useState(false);
  const [candidates, setCandidates] = useState([]), [target, setTarget] = useState(''), [error, setError] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const refresh = async () => {const [d,c] = await Promise.all([api.family(),api.familyCandidates()]);setData(d);setCandidates(c);setError('');};
  useEffect(() => {refresh().catch(e => setError(e.message));const t = setInterval(() => refresh().catch(() => {}), 15000);return () => clearInterval(t);}, []);
  const act = async fn => {if(busy)return;setBusy(true);try{await fn();await refresh();api.me().then(setMe).catch(() => {});toast('ثبت شد');}catch(e){toast(e.message);}finally{setBusy(false);}};
  if (!data) return <div className="card"><p>{error || 'در حال دریافت خانواده…'}</p>{error && <button className="btn ghost" onClick={() => refresh().catch(e => setError(e.message))}>تلاش دوباره</button>}</div>;
  const live = data.marriages.find(m => ['proposed','accepted','active'].includes(m.status));
  const mine = data.children.filter(c => c.status !== 'succeeded');
  const s = data.settings;
  return <section className="family-page">
    <h1 className="page-title">خاندان و خانواده</h1><p className="page-sub">پیوند امروز، نسل فردای خاندان</p>
    <div className="family-tabs" role="tablist" aria-label="بخش‌های خانواده">{[['marriage','ازدواج'],['children','فرزندان'],['heir','جانشینی']].map(([v,t]) => <button key={v} role="tab" aria-selected={tab===v} onClick={() => setTab(v)} className={tab===v?'on':''}><FamilyIcon kind={v} />{t}{v === 'children' && mine.length ? ` (${fa(mine.length)})` : ''}</button>)}</div>
    {tab === 'marriage' && <>
      {live ? <article className="card"><div className="family-heading"><FamilyIcon kind="marriage" /><h2 className="sect">{live.parents.map(p=>p.name).join(' و ')}</h2><span className="family-tag">{labels[live.status]}</span></div><p className="page-sub">سهم هر طرف: {fa(live.half_cost.gold)} طلا و {fa(live.half_cost.wine)} شراب</p>{live.status !== 'active' && <p className="page-sub">مهلت باقی‌مانده: {remaining(live.expires_at)} · مبلغ تا تصمیم نهایی رزرو است.</p>}
      {live.status === 'active' && <p>فرزندان به‌تدریج در فاصله‌های ۲۴ تا ۴۸ ساعت بازی متولد می‌شوند. هر پیوند ۲ تا ۴ فرزند خواهد داشت.</p>}
      {live.status === 'proposed' && <div className="grid2"><button disabled={busy} className="btn ghost" onClick={()=>act(()=>api.familyRespond(live.id,false))}>{live.parents[0].key === data.character_key ? 'پس گرفتن درخواست' : 'رد درخواست'}</button>{live.parents[1].key === data.character_key && <button className="btn" disabled={busy} onClick={()=>act(()=>api.familyRespond(live.id,true))}>قبول و رزرو سهم من</button>}</div>}</article>
      : <form className="card" onSubmit={e=>{e.preventDefault();act(async()=>{await api.familyPropose(Number(target),requestId);setRequestId(crypto.randomUUID());});}}><div className="family-heading"><FamilyIcon kind="marriage" /><h2 className="sect">درخواست ازدواج</h2></div><label className="f">طرف پیوند<select required value={target} onChange={e=>setTarget(e.target.value)}><option value="">انتخاب لرد یا لیدی</option>{candidates.map(p=><option key={p.tg_id} value={p.tg_id}>{p.name} · {p.castle}</option>)}</select></label>{!candidates.length && <p className="page-sub">کاراکتر واجد شرایطی برای درخواست در دسترس نیست.</p>}<p>سهم تو: {fa(s.marriage_gold/2)} طلا و {fa(s.marriage_wine/2)} شراب</p><p className="page-sub">پس از قبول طرف مقابل، مدیریت پیوند را تأیید می‌کند. با رد یا پایان مهلت، سهم‌های رزروشده کامل بازمی‌گردند.</p><button className="btn" disabled={busy || !target}>ارسال درخواست و رزرو سهم من</button></form>}
      <details className="card family-rules"><summary>قوانین خانواده و آموزش</summary><p>هزینهٔ ازدواج مساوی است. محل تولد فقط قلعهٔ اصلی یکی از والدین است؛ تقسیم بین والدین تصادفی و متعادل انجام می‌شود.</p><p>والد مسئول نام را می‌نویسد و هزینهٔ هر چهار مرحلهٔ رشد را می‌دهد. بلوغ چهار روز بازی بعد از تولد است؛ آموزشِ انجام‌نشده رشد را متوقف نمی‌کند.</p><p>نام پیش از بلوغ قابل ویرایش است. اگر نام‌گذاری فراموش شود، هنگام بلوغ یک نام پیش‌فرض ثبت می‌شود؛ والد مسئول یک بار امکان تغییر آن را دارد؛ تغییر بعدی با مدیریت است.</p><p>آموزش‌ها در پرونده ثبت می‌شوند و فعلاً ضریب اضافهٔ اقتصادی یا رزمی ندارند. با مرگ یکی از همسران، تولدهای آیندهٔ آن پیوند متوقف می‌شود. زمان‌ها هنگام توقف بازی ثابت می‌مانند.</p><p>خانواده و وارثان مربوط به همین فصل‌اند و با شروع فصل تازه پاک می‌شوند.</p></details>
      {data.marriages.filter(m=>!['proposed','accepted','active'].includes(m.status)).map(m=><div className="card" key={m.id}><h3 className="sect">{m.parents.map(p=>p.name).join(' و ')}</h3><p className="page-sub">{labels[m.status]} · {m.reason}</p></div>)}
    </>}
    {tab === 'children' && <>{!mine.length && <div className="card family-empty"><FamilyIcon /><p>هنوز فرزندی در این خانواده متولد نشده است.</p></div>}{mine.map(c=><ChildCard key={c.id} child={c} ownKey={data.character_key} stages={data.stages} act={act} busy={busy}/>)}</>}
    {tab === 'heir' && <><div className="card"><div className="family-heading"><FamilyIcon kind="heir" /><h2 className="sect">{data.succession.heir ? `وارث اصلی: ${data.succession.heir.name}` : 'وارث بالغ نداری'}</h2></div><p>{data.succession.heir ? 'با مرگ کاراکتر، این وارث ادامه‌دهندهٔ بازی است. قلعه‌ها، منابع، لشکرها، پروژه‌ها، امتیازها و مدال‌ها حفظ می‌شوند.' : data.succession.has_minors ? 'به‌دلیل به بلوغ نرسیدن وراث، در صورت مرگ قلعه‌ها آزاد و فعالیت‌ها لغو می‌شوند.' : 'بدون وارث بالغ، مرگ کاراکتر باعث آزاد شدن قلعه‌ها و لغو فعالیت‌ها می‌شود.'}</p><p className="page-sub">قدیمی‌ترین وارث بالغ اولویت دارد. مدیریت می‌تواند مرگ کاراکتر همراه تمام وارثان وابسته را ثبت کند؛ در آن حالت جانشینی انجام نمی‌شود.</p></div>{data.succession.children.map(c=><div className="card family-heading" key={c.id}><FamilyIcon kind="heir"/><div><h3 className="sect">{c.name}</h3><p className="page-sub">{c.id===data.succession.heir?.id?'وارث اصلی':time(c.adult_at)<=gameNow()?'وارث ذخیره':`تا بلوغ: ${remaining(c.adult_at)}`} · {c.residence}</p></div></div>)}</>}
  </section>;
}

export function AdminFamily() {
  const {toast}=useGame();const [data,setData]=useState(null),[settings,setSettings]=useState(null),[busy,setBusy]=useState(false),[reason,setReason]=useState({});
  const refresh=async()=>{const d=await api.adminFamily();setData(d);setSettings(d.settings);};
  useEffect(()=>{refresh().catch(e=>toast(e.message));},[]);
  const act=async fn=>{if(busy)return;setBusy(true);try{await fn();await refresh();toast('ثبت شد');}catch(e){toast(e.message);}finally{setBusy(false);}};
  if(!data)return <p className="page-sub">در حال دریافت خانواده‌ها…</p>;
  return <div className="family-page"><form className="card" onSubmit={e=>{e.preventDefault();act(()=>api.adminFamilySettings(settings));}}><h2 className="sect">هزینه‌های ازدواج و پرورش</h2><div className="grid2">{[['marriage_gold','طلای کل ازدواج'],['marriage_wine','شراب کل ازدواج'],['training_gold','طلای هر روز آموزش'],['training_food','غذای هر روز آموزش']].map(([k,t])=><label className="f" key={k}>{t}<input type="number" min="0" max="1000000" step={k.startsWith('marriage')?2:1} required value={settings[k]} onChange={e=>setSettings({...settings,[k]:Number(e.target.value)})}/></label>)}</div><p className="page-sub">هزینهٔ ازدواج نصف می‌شود. تغییر نرخ روی درخواست‌ها و پیوندهای قبلی اثر ندارد. آموزش فقط از والد مسئول کسر می‌شود.</p><button className="btn" disabled={busy}>ذخیرهٔ هزینه‌ها</button></form><h2 className="sect">درخواست‌های منتظر تأیید</h2>{!data.requests.length&&<p className="page-sub">درخواستی منتظر نیست.</p>}{data.requests.map(m=><article className="card" key={m.id}><div className="family-heading"><FamilyIcon kind="marriage"/><h3 className="sect">{m.parents.map(p=>p.name).join(' و ')}</h3></div><p className="page-sub">سهم هر طرف رزرو شده: {fa(m.half_cost.gold)} طلا · {fa(m.half_cost.wine)} شراب</p><label className="f">دلیل رد درخواست<input value={reason[m.id]||''} maxLength={500} onChange={e=>setReason({...reason,[m.id]:e.target.value})}/></label><div className="grid2"><button className="btn ghost" disabled={busy||!reason[m.id]?.trim()} onClick={()=>act(()=>api.adminFamilyReview(m.id,false,reason[m.id]))}>رد و بازگشت هزینه</button><button className="btn" disabled={busy} onClick={()=>act(()=>api.adminFamilyReview(m.id,true,''))}>تأیید ازدواج</button></div></article>)}<details className="card"><summary>ویرایش نام فرزندان</summary>{data.children.map(c=><ChildCard key={c.id} child={c} stages={[]} admin busy={busy} act={act}/>)}</details></div>;
}
