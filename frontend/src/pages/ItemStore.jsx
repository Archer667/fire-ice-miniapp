import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { Cart, Coin, Warehouse } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { ITEM_RARITY_HEX, ITEM_RARITY_COLORS, ITEM_TYPES } from '../gamedata.js';
import '../styles/item-store.css';

const STATUS = { preparing: 'در حال آماده‌سازی', open: 'آمادهٔ معامله', pending: 'در انتظار تأیید', sold: 'فروخته‌شده', cancelled: 'لغوشده', rejected: 'ردشده', unsold: 'بدون پیشنهاد', expired: 'منقضی‌شده' };
const number = n => Number(n || 0).toLocaleString('fa-IR');
const currency = c => c === 'gold' ? 'سکه' : 'تومان';
const money = (n, c) => `${number(n)} ${currency(c)}`;
const stamp = iso => iso ? new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z') : null;
const date = iso => iso ? stamp(iso).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran', dateStyle: 'short', timeStyle: 'short' }) : '—';

function useRequestIds() {
  const keys = useRef(new Map());
  return payload => { const key = JSON.stringify(payload); if (!keys.current.has(key)) keys.current.set(key, crypto.randomUUID()); return keys.current.get(key); };
}

export function ItemPicture({ item, large = false }) {
  return <div className={`store-picture ${large ? 'large' : ''}`} style={{ '--rarity': ITEM_RARITY_HEX[item?.color] || '#dab36a' }}>
    {item?.image ? <img src={item.image} alt={item.name || 'تصویر آیتم'} loading="lazy" /> : <Warehouse s={large ? 38 : 25} />}
  </div>;
}

function Remaining({ endsAt, offset }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const ms = stamp(endsAt).getTime() - now - offset;
  const minutes = Math.max(0, Math.ceil(ms / 60000));
  return <span className="store-countdown">{ms <= 0 ? 'پایان مزایده؛ در حال تعیین نتیجه' : `${number(Math.floor(minutes / 60))} ساعت و ${number(minutes % 60)} دقیقه`}</span>;
}

export function ListingForm({ items, onSubmit, busy, cfg }) {
  const [grantId, setGrantId] = useState('');
  const [kind, setKind] = useState('fixed');
  const [price, setPrice] = useState('');
  const [hours, setHours] = useState('24');
  const chosen = items?.find(it => it.id === grantId);
  return <form className="card store-form" onSubmit={e => { e.preventDefault(); onSubmit({ grant_id: grantId, kind, price: Number(price), duration_hours: Number(hours) }); }}>
    <div className="store-section-title"><Cart s={19} /><h3>عرضهٔ آیتم</h3></div>
    <p className="page-sub">آیتم تا پایان معامله رزرو می‌شود و قابل استفاده یا همراهی با لشکر نیست. اعتبار آیتم‌های موقت تمدید نمی‌شود.</p>
    <label className="f">آیتم<select required value={grantId} onChange={e => setGrantId(e.target.value)}><option value="">انتخاب از دارایی‌ها</option>{(items || []).filter(it => !it.campaign_id).map(it => <option key={it.id} value={it.id}>{it.name}</option>)}</select></label>
    {chosen && <div className="store-selected"><ItemPicture item={chosen} /><div><b>{chosen.name}</b><small>{chosen.type_name}</small></div></div>}
    <label className="f">روش فروش<select value={kind} onChange={e => setKind(e.target.value)}><option value="fixed">قیمت قطعی</option><option value="auction">مزایده</option></select></label>
    <div className="store-fields"><label className="f">{kind === 'auction' ? 'قیمت آغاز مزایده' : 'قیمت فروش'} · {currency(cfg?.currency)}<input required type="number" min="1" max="1000000000000" step="1" inputMode="numeric" value={price} onChange={e => setPrice(e.target.value)} /></label>
      {kind === 'auction' && <label className="f">مدت · ساعت واقعی<select value={hours} onChange={e => setHours(e.target.value)}>{[1,6,12,24,48,72,168].map(n => <option key={n} value={n}>{number(n)} ساعت</option>)}</select></label>}</div>
    {kind === 'auction' && <p className="page-sub">گام پیشنهاد: {money(cfg?.[`${cfg?.currency}_step`], cfg?.currency)}. مزایده هنگام توقف بازی هم ادامه دارد.</p>}
    <button className="btn" disabled={busy || !grantId || !cfg?.enabled}>{busy ? 'در حال ثبت…' : 'ثبت آگهی فروش'}</button>
    {!items?.length && <p className="page-sub">آیتم آزاد برای عرضه موجود نیست.</p>}
  </form>;
}

function StoreCard({ row, offset, disabled, onOffer, onCancel, admin, onDecision, onEdit }) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [paid, setPaid] = useState(false);
  const [edit, setEdit] = useState(false);
  const [price, setPrice] = useState(String(row.price));
  const [hours, setHours] = useState('24');
  const item = row.item || {};
  const ended = row.ends_at && stamp(row.ends_at).getTime() <= Date.now() + offset;
  return <article className={`store-card ${row.status === 'pending' ? 'awaiting' : ''}`}>
    <div className="store-card-head"><ItemPicture item={item} large /><div className="store-card-title"><span className="store-eyebrow">{row.kind === 'auction' ? 'مزایدهٔ زنده' : 'فروش با قیمت قطعی'}</span><h3>{item.name}</h3><span className="store-rarity" style={{ color: ITEM_RARITY_HEX[item.color] }}>{ITEM_RARITY_COLORS[item.color] || 'معمولی'} · {ITEM_TYPES[item.type] || item.type}</span></div></div>
    {item.description && <p className="store-description">{item.description}</p>}
    <div className="store-price"><span>{row.kind === 'auction' && row.highest_amount ? 'بالاترین پیشنهاد' : row.kind === 'auction' ? 'شروع از' : 'قیمت آیتم'}</span><strong>{money(row.highest_amount || row.price, row.currency)}</strong></div>
    <div className="store-meta"><span>فروشنده: {row.seller_name}{row.mine ? ' · آگهی شما' : ''}</span><span className={`store-status ${row.status}`}>{STATUS[row.status] || row.status}</span></div>
    {row.kind === 'auction' && <div className="store-meta"><span>{number(row.bid_count)} پیشنهاد · گام {money(row.bid_step, row.currency)}</span>{row.status === 'open' ? <Remaining endsAt={row.ends_at} offset={offset} /> : <span>پایان: {date(row.ends_at)}</span>}</div>}
    {row.expires_at && <p className="page-sub">اعتبار آیتم تا زمان داخلی بازی: {date(row.expires_at)}</p>}
    {row.my_offer && <p className="store-highlight">{row.status === 'pending' ? 'خرید شما در انتظار بررسی است.' : 'پیشنهاد برتر متعلق به شماست.'}{row.currency === 'gold' && row.status !== 'sold' ? ' سکه تا تعیین نتیجه رزرو است.' : ''}</p>}
    {row.reason && <p className="store-description">{row.reason}</p>}
    {admin && row.review_error && <p className="store-highlight">نیازمند رسیدگی: {row.review_error}</p>}
    {!admin && row.status === 'open' && !row.mine && <form className="store-offer" onSubmit={e => { e.preventDefault(); const next = row.kind === 'fixed' ? row.price : Number(amount || row.minimum_offer); if (window.confirm(`${row.kind === 'auction' ? 'ثبت پیشنهاد' : 'ثبت خرید'} به مبلغ ${money(next, row.currency)}؟ ${row.currency === 'gold' ? 'سکه تا تعیین نتیجه رزرو می‌شود.' : 'پرداخت با هماهنگی پشتیبانی پیگیری می‌شود.'}`)) onOffer(row, next); }}>
      {row.kind === 'auction' && <label className="f">پیشنهاد شما · {currency(row.currency)}<input type="number" required min={row.minimum_offer} max="1000000000000" step={row.bid_step} value={amount || row.minimum_offer} onChange={e => setAmount(e.target.value)} /></label>}
      <button className="btn" disabled={disabled || ended}>{ended ? 'زمان پیشنهاد پایان یافته' : row.kind === 'auction' ? 'ثبت پیشنهاد بالاتر' : 'درخواست خرید'}</button>
    </form>}
    {!admin && row.mine && row.status === 'open' && !row.bid_count && <button className="btn ghost" disabled={disabled} onClick={() => { if (window.confirm('آگهی لغو و آیتم به دارایی‌ها برگردد؟')) onCancel(row); }}>لغو آگهی</button>}
    {admin && <details className="store-admin-details"><summary>رسیدگی و مدیریت آگهی</summary>
      <dl><dt>فروشنده</dt><dd>{row.seller?.name} · {row.seller?.tg_id}</dd><dt>خریدار / پیشنهاد برتر</dt><dd>{row.highest ? `${row.highest.person.name} · ${row.highest.person.tg_id}` : '—'}</dd><dt>مبلغ</dt><dd>{money(row.highest_amount || row.price, row.currency)}</dd><dt>ثبت</dt><dd>{date(row.created_at)}</dd></dl>
      {!!row.bid_history?.length && <details><summary>تاریخچهٔ پیشنهادها</summary>{row.bid_history.map((b,i) => <p className="page-sub" key={i}>{b.person.name} · {money(b.amount,row.currency)} · {date(b.at)}</p>)}</details>}
      {row.status === 'pending' && <>{row.currency === 'toman' && <label className="store-check"><input type="checkbox" checked={paid} onChange={e => setPaid(e.target.checked)} /> پرداخت تومانی بررسی و تأیید شده است.</label>}<button className="btn" disabled={disabled || (row.currency === 'toman' && !paid)} onClick={() => { if(window.confirm('خرید نهایی و آیتم به خریدار منتقل شود؟')) onDecision(row,'approve','',paid); }}>تأیید نهایی و انتقال آیتم</button></>}
      {['open','pending','preparing'].includes(row.status) && <><label className="f">دلیل رد یا حذف<textarea maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label><button className="btn store-danger" disabled={disabled || !reason.trim()} onClick={() => { if(window.confirm('آگهی بسته شود؟ وجه رزروشده و آیتم به صاحبانشان برمی‌گردند.')) onDecision(row,row.status === 'pending' ? 'reject' : 'cancel',reason); }}>{row.status === 'pending' ? 'رد خرید و بازگشت وجه' : 'حذف آگهی و بازگشت آیتم'}</button></>}
      {row.status === 'open' && !row.bid_count && <><button className="btn ghost" onClick={() => setEdit(!edit)}>اصلاح شرایط آگهی</button>{edit && <div className="store-form"><label className="f">قیمت · {currency(row.currency)}<input type="number" min="1" max="1000000000000" value={price} onChange={e => setPrice(e.target.value)} /></label>{row.kind === 'auction' && <label className="f">مدت تازه از اکنون · ساعت<input type="number" min="1" max="720" value={hours} onChange={e => setHours(e.target.value)} /></label>}<button className="btn" disabled={disabled || Number(price)<1} onClick={() => onEdit(row,{price:Number(price),duration_hours:Number(hours)})}>ذخیره اصلاحات</button></div>}</>}
    </details>}
  </article>;
}

export default function ItemStore() {
  const { toast, setMe } = useGame();
  const [tab,setTab] = useState('market');
  const [data,setData] = useState(null);
  const [items,setItems] = useState([]);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const [search,setSearch] = useState('');
  const [kind,setKind] = useState('all');
  const [offset,setOffset] = useState(0);
  const idFor = useRequestIds();
  async function load(append=false) { try { const result=await api.itemStore(tab==='mine'?'mine':'market',append?offset:0); result.clockOffset=stamp(result.real_now).getTime()-Date.now();setData(d=>({...result,rows:append?[...(d?.rows||[]),...result.rows]:result.rows}));setOffset(append?offset+40:40);setError(''); } catch(e){setError(e.message);} }
  useEffect(()=>{setData(null);load(); if(tab==='sell')api.myItems().then(setItems).catch(e=>toast(e.message));},[tab]);
  useEffect(()=>{if(tab==='sell')return;const timer=setInterval(()=>{if(document.visibilityState==='visible')load();},15000);return()=>clearInterval(timer);},[tab]);
  async function action(fn,message) {setBusy(true);try{await fn();toast(message);await load();api.myItems().then(setItems).catch(()=>{});api.me().then(setMe).catch(()=>{});}catch(e){toast(e.message);await load();}finally{setBusy(false);}}
  const rows=(data?.rows||[]).filter(r=>(kind==='all'||r.kind===kind)&&`${r.item?.name} ${r.seller_name}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="item-store"><header className="store-hero"><span className="store-emblem"><Cart s={28}/></span><div><span className="store-eyebrow">گنجینه‌های خاندان‌ها</span><h1>{data?.settings?.title||'بازار گنجینه‌ها'}</h1><p>{data?.settings?.description||'آیتم‌های کمیاب؛ فروش مستقیم و مزایده'}</p></div></header>
    <div className="tabs store-tabs">{[['market','ویترین فروشگاه'],['mine','معامله‌های من'],['sell','فروش آیتم']].map(([key,label])=><button key={key} className={`rbtn tab ${tab===key?'on':''}`} onClick={()=>setTab(key)}>{label}</button>)}</div>
    <div className="store-policy"><Coin s={16}/><p>خرید پس از تأیید پشتیبانی نهایی می‌شود. در معاملهٔ سکه‌ای، وجه رزرو و در صورت رد برگردانده می‌شود. پرداخت تومانی با هماهنگی پشتیبانی انجام می‌شود.</p></div>
    {error&&<div className="card" role="alert">{error}<button className="btn ghost" onClick={()=>load()}>تلاش دوباره</button></div>}
    {!data&&!error&&<div className="store-skeleton">در حال آماده‌سازی ویترین…</div>}
    {data&&!data.settings.enabled&&<p className="store-highlight">ثبت و خرید آگهی موقتاً متوقف است. وضعیت معامله‌های قبلی در «معامله‌های من» قابل پیگیری است.</p>}
    {data&&tab==='sell'?<ListingForm items={items} busy={busy} cfg={data.settings} onSubmit={body=>action(()=>api.storeCreate({...body,request_id:idFor(body)}),'آگهی ثبت شد')}/>:data&&<><div className="store-toolbar"><input aria-label="جست‌وجوی آیتم" placeholder="نام آیتم یا فروشنده…" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="نوع فروش" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">همهٔ آگهی‌ها</option><option value="fixed">قیمت قطعی</option><option value="auction">مزایده</option></select></div><div className="store-grid">{rows.map(row=><StoreCard key={row.id} row={row} offset={data.clockOffset||0} disabled={busy||!data.settings.enabled} onOffer={(r,amount)=>{const body={amount,version:r.version};return action(()=>api.storeOffer(r.id,{...body,request_id:idFor({id:r.id,...body})}),r.kind==='auction'?'پیشنهاد ثبت شد':'خرید در انتظار تأیید قرار گرفت');}} onCancel={r=>action(()=>api.storeCancel(r.id),'آگهی لغو شد')}/>)}</div>{!rows.length&&<div className="card store-empty"><Warehouse s={30}/><b>آگهی‌ای برای نمایش نیست</b><p>آیتم‌های عرضه‌شده و وضعیت معامله‌ها در این بخش نمایش داده می‌شوند.</p></div>}{data.has_more&&<button className="btn ghost" onClick={()=>load(true)}>نمایش آگهی‌های بیشتر</button>}</>}
  </section>;
}

export function AdminItemStore() {
  const {toast}=useGame();const[data,setData]=useState(null);const[cfg,setCfg]=useState(null);const[busy,setBusy]=useState(false);const[error,setError]=useState('');const[filter,setFilter]=useState('pending');const[search,setSearch]=useState('');const[owner,setOwner]=useState([]);const[items,setItems]=useState([]);const[offset,setOffset]=useState(0);const idFor=useRequestIds();
  async function load(append=false){try{const r=await api.adminStore(append?offset:0,filter);r.clockOffset=stamp(r.real_now).getTime()-Date.now();setData(d=>({...r,rows:append?[...(d?.rows||[]),...r.rows]:r.rows}));setOffset(append?offset+60:60);setCfg(c=>c||r.settings);setError('');}catch(e){setError(e.message);}}
  useEffect(()=>{setData(null);load();},[filter]);
  useEffect(()=>{setItems([]);if(owner[0])api.adminStoreInventory(owner[0].tg_id).then(setItems).catch(e=>toast(e.message));},[owner[0]?.tg_id]);
  async function act(fn,text){setBusy(true);try{await fn();toast(text);await load();if(owner[0])api.adminStoreInventory(owner[0].tg_id).then(setItems).catch(()=>{});}catch(e){toast(e.message);}finally{setBusy(false);}}
  const rows=(data?.rows||[]).filter(r=>(filter==='all'||r.status===filter)&&`${r.item?.name} ${r.seller_name} ${r.highest?.person?.name||''}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="item-store"><header className="store-hero"><span className="store-emblem"><Cart s={28}/></span><div><span className="store-eyebrow">مدیریت معاملات</span><h2>فروشگاه آیتم‌ها</h2><p>{number(data?.pending_count)} خرید در انتظار تأیید</p></div></header>{error&&<div className="card" role="alert">{error}<button className="btn ghost" onClick={()=>load()}>تلاش دوباره</button></div>}
    {!!data?.unsettled?.length&&<div className="card"><strong>تسویه‌های نیازمند رسیدگی: {number(data.unsettled.length)}</strong><p className="page-sub">انتقال‌های نیمه‌تمام پیش از ادامهٔ معامله بررسی می‌شوند. پس از رفع مشکل حساب، ادامهٔ تسویه را اجرا کن.</p><button className="btn ghost" disabled={busy} onClick={()=>act(async()=>{const result=await api.adminStoreRecover();if(!result.ready)throw new Error('تسویه هنوز نیازمند بررسی حساب طرفین است');},'تسویه‌ها تکمیل شدند')}>ادامهٔ تسویه‌های نیمه‌تمام</button></div>}
    {cfg&&<details className="card store-settings"><summary>تنظیمات فروشگاه و گام مزایده</summary><label className="store-check"><input type="checkbox" checked={cfg.enabled} onChange={e=>setCfg({...cfg,enabled:e.target.checked})}/> ثبت و خرید آگهی فعال باشد</label><label className="f">عنوان<input maxLength={60} value={cfg.title} onChange={e=>setCfg({...cfg,title:e.target.value})}/></label><label className="f">معرفی کوتاه<textarea maxLength={300} value={cfg.description} onChange={e=>setCfg({...cfg,description:e.target.value})}/></label><label className="f">ارز آگهی‌های تازه<select value={cfg.currency} onChange={e=>setCfg({...cfg,currency:e.target.value})}><option value="toman">تومان · تسویه با پشتیبانی</option><option value="gold">سکهٔ بازی · رزرو خودکار</option></select></label><div className="store-fields"><label className="f">کف افزایش · تومان<input type="number" min="1" max="10000000000" value={cfg.toman_step} onChange={e=>setCfg({...cfg,toman_step:Number(e.target.value)})}/></label><label className="f">کف افزایش · سکه<input type="number" min="1" max="10000000000" value={cfg.gold_step} onChange={e=>setCfg({...cfg,gold_step:Number(e.target.value)})}/></label></div><p className="page-sub">ارز و گام پیشنهاد آگهی‌های قبلی ثابت می‌مانند. زمان مزایده واقعی است و با توقف بازی متوقف نمی‌شود.</p><button className="btn" disabled={busy} onClick={()=>act(()=>api.adminStoreSettings(cfg),'تنظیمات ذخیره شد')}>ذخیره تنظیمات</button></details>}
    {cfg&&<details className="card store-settings"><summary>افزودن آگهی از دارایی بازیکن</summary><label className="f">فروشنده</label><PlayerPicker value={owner} onChange={setOwner} single/>{owner[0]&&<ListingForm items={items} busy={busy} cfg={cfg} onSubmit={body=>act(()=>api.adminStoreCreate(owner[0].tg_id,{...body,request_id:idFor({uid:owner[0].tg_id,...body})}),'آگهی ثبت شد')}/>}</details>}
    <div className="store-toolbar"><input aria-label="جست‌وجوی معامله" placeholder="نام آیتم، خریدار یا فروشنده…" value={search} onChange={e=>setSearch(e.target.value)}/><select value={filter} aria-label="وضعیت معامله" onChange={e=>setFilter(e.target.value)}><option value="all">تمام آگهی‌ها</option>{Object.entries(STATUS).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><button className="btn ghost" onClick={()=>load()}>تازه‌سازی</button></div>
    <div className="store-grid">{rows.map(row=><StoreCard key={`${row.id}:${row.version}`} row={row} offset={data.clockOffset||0} disabled={busy} admin onDecision={(r,action,reason,payment_confirmed)=>act(()=>api.adminStoreDecision(r.id,{action,reason,payment_confirmed}),action==='approve'?'آیتم منتقل و خرید نهایی شد':'آگهی بسته و تسویه انجام شد')} onEdit={(r,body)=>act(()=>api.adminStoreEdit(r.id,body),'آگهی اصلاح شد')}/>)}</div>{data&&!rows.length&&<div className="card store-empty">معامله‌ای در این وضعیت وجود ندارد.</div>}{data?.has_more&&<button className="btn ghost" onClick={()=>load(true)}>نمایش سوابق بیشتر</button>}
  </section>;
}
