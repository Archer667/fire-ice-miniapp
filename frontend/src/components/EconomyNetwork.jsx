import {useEffect, useMemo, useState} from 'react';
import {api} from '../api.js';
import {useGame} from '../store.jsx';
import PlayerPicker from './PlayerPicker.jsx';
import {CARAVAN_GOODS, TRADE_GOOD_NAMES} from '../gamedata.js';

const fa=value=>Number(value||0).toLocaleString('fa-IR');
const GOODS=CARAVAN_GOODS.filter(key=>key!=='gold');
const STATUS={pending:'منتظر پاسخ',active:'فعال',completed:'کامل‌شده',rejected:'ردشده',cancelled:'پس‌گرفته‌شده',breached:'نقض‌شده',admin_closed:'بسته‌شده'};

export default function EconomyNetwork(){
  const {me,setMe,toast}=useGame();
  const [section,setSection]=useState('orders');
  const [orders,setOrders]=useState(null);
  const [contracts,setContracts]=useState(null);
  const [meta,setMeta]=useState(null),[error,setError]=useState('');
  const [busy,setBusy]=useState('');
  const [order,setOrder]=useState({resource:'food',qty:100,unit_price:10});
  const [fillQty,setFillQty]=useState({});
  const [seller,setSeller]=useState([]);
  const [contract,setContract]=useState({resource:'food',qty_per_delivery:100,unit_price:10,deliveries:3,interval_hours:24,note:''});
  const load=()=>Promise.all([api.economyMeta().then(setMeta),api.economyOrders().then(setOrders),api.economyContracts().then(setContracts)]).then(()=>setError('')).catch(e=>{setError(e.message);toast(e.message);});
  useEffect(()=>{load();},[]);
  const mine=useMemo(()=>(orders||[]).filter(row=>row.mine),[orders]);
  const available=useMemo(()=>(orders||[]).filter(row=>!row.mine),[orders]);
  const action=async(key,fn,message)=>{setBusy(key);try{const result=await fn();toast(message);await load();api.me().then(setMe).catch(()=>{});return result;}catch(e){toast(e.message);}finally{setBusy('');}};
  const allowed=(resource,price)=>meta&&Number(price)>=(meta.prices[resource]??1)&&(meta.ceilings[resource]==null||Number(price)<=meta.ceilings[resource]);
  const enabled=!!meta?.rules.trade_network_enabled;
  const range=(resource)=>`حداقل ${fa(meta?.prices[resource])} سکه · حداکثر ${meta?.ceilings[resource]==null?'بدون سقف':fa(meta.ceilings[resource])+' سکه'}`;
  const createOrder=()=>action('new-order',()=>api.economyCreateOrder({...order,qty:Number(order.qty),unit_price:Number(order.unit_price)}),'سفارش خرید ثبت شد و مبلغ آن در امانت ماند');
  const createContract=()=>{
    if(!seller[0])return toast('فروشنده را انتخاب کن');
    return action('new-contract',()=>api.economyCreateContract({...contract,seller_id:seller[0].tg_id,qty_per_delivery:Number(contract.qty_per_delivery),unit_price:Number(contract.unit_price),deliveries:Number(contract.deliveries),interval_hours:Number(contract.interval_hours)}),'پیشنهاد قرارداد برای فروشنده فرستاده شد').then(()=>setSeller([]));
  };
  return <section className="economy-network">
    <header className="network-head"><div><span>بازار توافقی</span><h2>سفارش خرید و قرارداد تأمین</h2><p>برای خرید کالا اعلام نیاز کن یا تحویل‌های منظم را با یک خاندان قرارداد ببند.</p></div><b>{fa(me.resources?.gold)}<small> سکه</small></b></header>
    {error&&<div className="card" role="alert">{error}<button className="btn ghost" onClick={load}>تلاش دوباره</button></div>}
    {meta&&<div className="card"><p>کارمزد سفارش‌ها {fa(meta.rules.market_fee_percent)}٪ است؛ معاملهٔ بین دو اقلیم {fa(meta.rules.cross_region_tariff_percent)}٪ عوارض اضافه دارد. مبلغ از دریافتی فروشنده کسر می‌شود.</p><p>{meta.rules.contract_fees_enabled?'تحویل قرارداد هم مشمول همین کارمزد و عوارض است.':'تحویل قرارداد تأمین کارمزد ندارد.'} قیمت هر کالا هنگام ثبت و اجرا با بازهٔ مجاز همان روز بررسی می‌شود.</p>{!enabled&&<p>معاملهٔ تازه فعلاً متوقف است؛ لغو و بازپرداخت در دسترس است.</p>}</div>}
    <nav className="network-tabs"><button className={section==='orders'?'on':''} onClick={()=>setSection('orders')}>سفارش‌های خرید</button><button className={section==='contracts'?'on':''} onClick={()=>setSection('contracts')}>قراردادهای تأمین</button></nav>
    {section==='orders'&&<>
      <details className="card network-create"><summary>ثبت سفارش خرید</summary><div className="network-form three"><label>کالا<select value={order.resource} onChange={e=>setOrder({...order,resource:e.target.value})}>{GOODS.map(g=><option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}</select></label><label>تعداد<input type="number" min="1" value={order.qty} onChange={e=>setOrder({...order,qty:e.target.value})}/></label><label>قیمت هر واحد<input type="number" min="1" value={order.unit_price} onChange={e=>setOrder({...order,unit_price:e.target.value})}/></label></div><p>{range(order.resource)}</p><div className="network-total"><span>مبلغ امانت</span><strong>{fa(order.qty*order.unit_price)} سکه</strong></div><p>این مبلغ هنگام ثبت کنار گذاشته می‌شود. با تأمین سفارش به فروشنده می‌رسد و با لغو، مانده‌اش برمی‌گردد.</p><button className="btn" disabled={!!busy||!enabled||!allowed(order.resource,order.unit_price)} onClick={createOrder}>ثبت سفارش</button></details>
      <div className="sect">درخواست‌های بازار</div><div className="network-grid">{available.map(row=><article className="card network-order" key={row.id}><header><b>{row.resource_name}</b><span>{fa(row.unit_price)} سکه / واحد</span></header><p><strong>{row.buyer_name}</strong> خریدار {fa(row.remaining)} واحد است.</p><p>{range(row.resource)}{!allowed(row.resource,row.unit_price)&&' · این سفارش خارج از بازهٔ مجاز است'}</p><label>مقدار تأمین<input type="number" min="1" max={row.remaining} value={fillQty[row.id]||1} onChange={e=>setFillQty(v=>({...v,[row.id]:e.target.value}))}/></label><button className="btn" disabled={!!busy||!enabled||!allowed(row.resource,row.unit_price)} onClick={()=>action('fill:'+row.id,()=>api.economyFillOrder(row.id,Number(fillQty[row.id]||1)),'کالا تحویل شد و مبلغ فروش به خزانه‌ات آمد')}>تأمین سفارش</button></article>)}{available.length===0&&<div className="card network-empty">درخواستی برای تأمین وجود ندارد.</div>}</div>
      {!!mine.length&&<><div className="sect">سفارش‌های من</div><div className="network-grid">{mine.map(row=><article className="card network-order mine" key={row.id}><header><b>{row.resource_name}</b><span>{fa(row.unit_price)} سکه / واحد</span></header><p>{fa(row.remaining)} واحد از {fa(row.qty)} واحد باقی مانده است.</p><button className="btn ghost" disabled={!!busy} onClick={()=>action('cancel:'+row.id,()=>api.economyCancelOrder(row.id),'سفارش بسته شد و ماندهٔ امانت برگشت')}>لغو و بازگرداندن مانده</button></article>)}</div></>}
    </>}
    {section==='contracts'&&<>
      <details className="card network-create"><summary>پیشنهاد قرارداد تأمین</summary><label className="f">فروشنده</label><PlayerPicker value={seller} onChange={setSeller} single placeholder="نام فروشنده را جست‌وجو کن…"/><div className="network-form"><label>کالا<select value={contract.resource} onChange={e=>setContract({...contract,resource:e.target.value})}>{GOODS.map(g=><option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}</select></label><label>هر نوبت<input type="number" min="1" value={contract.qty_per_delivery} onChange={e=>setContract({...contract,qty_per_delivery:e.target.value})}/></label><label>قیمت هر واحد<input type="number" min="1" value={contract.unit_price} onChange={e=>setContract({...contract,unit_price:e.target.value})}/></label><label>تعداد تحویل<input type="number" min="1" max="30" value={contract.deliveries} onChange={e=>setContract({...contract,deliveries:e.target.value})}/></label><label>فاصلهٔ تحویل (ساعت بازی)<input type="number" min="1" max="720" value={contract.interval_hours} onChange={e=>setContract({...contract,interval_hours:e.target.value})}/></label></div><label className="f">توضیح قرارداد</label><textarea maxLength="500" rows="3" value={contract.note} onChange={e=>setContract({...contract,note:e.target.value})}/><p>{range(contract.resource)}</p><div className="network-total"><span>کل مبلغ امانت</span><strong>{fa(contract.qty_per_delivery*contract.unit_price*contract.deliveries)} سکه</strong></div><button className="btn" disabled={!!busy||!enabled||!allowed(contract.resource,contract.unit_price)} onClick={createContract}>فرستادن پیشنهاد</button></details>
      <div className="network-grid">{(contracts||[]).map(row=><article className={`card network-contract ${row.status}`} key={row.id}><header><div><b>{row.resource_name}</b><small>{row.mine_as==='buyer'?`فروشنده: ${row.seller_name}`:`خریدار: ${row.buyer_name}`}</small></div><span>{STATUS[row.status]||row.status}</span></header><p>{fa(row.qty_per_delivery)} واحد در هر نوبت · {fa(row.delivered)} از {fa(row.deliveries)} تحویل · هر واحد {fa(row.unit_price)} سکه</p>{row.note&&<blockquote>{row.note}</blockquote>}<div className="network-actions">{row.status==='pending'&&row.mine_as==='seller'&&<><button className="btn" disabled={!!busy||!enabled||!allowed(row.resource,row.unit_price)} onClick={()=>action('accept:'+row.id,()=>api.economyRespondContract(row.id,true),'قرارداد پذیرفته شد')}>پذیرفتن</button><button className="btn ghost" disabled={!!busy} onClick={()=>action('reject:'+row.id,()=>api.economyRespondContract(row.id,false),'قرارداد رد شد')}>رد کردن</button></>}{row.status==='pending'&&row.mine_as==='buyer'&&<button className="btn ghost" disabled={!!busy} onClick={()=>action('cancel-contract:'+row.id,()=>api.economyCancelContract(row.id),'پیشنهاد پس گرفته شد')}>پس‌گرفتن پیشنهاد</button>}{row.status==='active'&&row.mine_as==='seller'&&<button className="btn" disabled={!!busy||!enabled||!allowed(row.resource,row.unit_price)} onClick={()=>action('deliver:'+row.id,()=>api.economyDeliverContract(row.id),'تحویل ثبت شد')}>ثبت تحویل این نوبت</button>}</div></article>)}{contracts?.length===0&&<div className="card network-empty">هنوز قرارداد تأمینی نداری.</div>}{contracts===null&&<div className="card network-empty">در حال دریافت قراردادها…</div>}</div>
    </>}
  </section>;
}
