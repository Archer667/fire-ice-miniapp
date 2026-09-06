import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Wood, Rock, Pick, Wheat, Wine, Send } from '../components/Icons.jsx';
import { CARAVAN_GOODS, TRADE_GOOD_NAMES, castleLabel } from '../gamedata.js';

import Projects from './Projects.jsx';
import '../trade.css';

const RES_ICON = { gold: Coin, wood: Wood, stone: Rock, iron: Pick, food: Wheat, wine: Wine };

const TABS = [
  { key: 'market', label: 'بازارها', detail: 'خرید و فروش کالا', icon: Coin },
  { key: 'caravan', label: 'کاروان', detail: 'تجارت با هم‌پیمان', icon: Send },
  { key: 'projects', label: 'پروژه‌ها', detail: 'سرمایه‌گذاری و بازده', icon: Pick },
];
const fa = value => Number(value || 0).toLocaleString('fa-IR');

function MarketCard({ item, kind, value, onQuantity, onBuy, onCancel, busy }) {
  const Icon = RES_ICON[item.resource] || Coin;
  const qty = value || 1;
  return <article className={`card exchange-card ${kind}`}>
    <header><span className="exchange-icon"><Icon s={24} /></span><div><h3>{item.name}</h3><p>{kind === 'player' ? `فروشنده: ${item.seller_name}` : kind === 'black' ? 'عرضهٔ محدود بازار سیاه' : 'عرضهٔ رسمی وستروس'}</p></div><span className="exchange-tag">{kind === 'official' ? 'شناور' : 'قیمت ثابت'}</span></header>
    <div className="exchange-quote"><div><span>قیمت هر واحد</span><strong>{fa(item.price)} <small>سکه</small></strong></div><div><span>موجودی</span><strong>{fa(item.qty)} <small>واحد</small></strong></div></div>
    {kind === 'official' && <p className="exchange-note"><span className={item.change_pct > 0 ? 'price-rise' : item.change_pct < 0 ? 'price-fall' : ''}>{item.change_pct > 0 ? '+' : ''}{fa(item.change_pct)}٪</span> نسبت به قیمت پایهٔ {fa(item.base_price)} سکه</p>}
    {kind === 'black' && <p className="exchange-note">مهلت خرید: {item.expires_in_minutes < 1 ? 'کمتر از یک دقیقه' : `${fa(Math.floor(item.expires_in_minutes / 60))} ساعت و ${fa(item.expires_in_minutes % 60)} دقیقه`}</p>}
    {item.mine ? <button className="btn ghost" disabled={busy} onClick={onCancel}>برداشتن آگهی و بازگشت کالا</button> : <form className="exchange-buy" onSubmit={e => { e.preventDefault(); onBuy(); }}>
      <label>تعداد خرید<input aria-label={`تعداد خرید ${item.name}`} type="number" inputMode="numeric" min="1" max={item.qty} step="1" required value={qty} onChange={e => onQuantity(e.target.value)} /></label>
      <button className="btn" disabled={busy || item.qty < 1}>{busy ? 'در حال خرید…' : <>خرید <span>{fa(qty * item.price)} سکه</span></>}</button>
    </form>}
  </article>;
}

const emptyAmounts = () => Object.fromEntries(CARAVAN_GOODS.map(g => [g, 0]));

export default function Trade() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState('market');

  const [marketSection, setMarketSection] = useState('official');
  const [sellPrice, setSellPrice] = useState(1);
  const [alliances, setAlliances] = useState(null);
  const [target, setTarget] = useState('');
  const [amounts, setAmounts] = useState(emptyAmounts());
  const [caravans, setCaravans] = useState(null);
  const [sendBusy, setSendBusy] = useState(false);

  const myCastles = [me.castle, ...(me.castles || [])];
  const [originCastle, setOriginCastle] = useState(me.castle);
  const [targetCastles, setTargetCastles] = useState([]);
  const [targetCastle, setTargetCastle] = useState('');
  const [routeOptions, setRouteOptions] = useState(null);
  const [routeChoice, setRouteChoice] = useState(0);
  const [routeError, setRouteError] = useState('');

  // با انتخابِ هم‌پیمان، قلعه‌های خودش رو می‌گیریم — چون ممکنه قلعهٔ دوم داشته باشه
  // و کاروان بخواد جای دیگه‌ای غیر از خونه‌اش برسه
  useEffect(() => {
    if (!target) { setTargetCastles([]); setTargetCastle(''); return; }
    let cancelled = false;
    api.playerCastles(Number(target)).then(list => {
      if (cancelled) return;
      setTargetCastles(list);
      setTargetCastle(list[0] || '');
    }).catch(() => { if (!cancelled) { setTargetCastles([]); setTargetCastle(''); } });
    return () => { cancelled = true; };
  }, [target]);

  useEffect(() => {
    if (!target || !originCastle || !targetCastle) {
      setRouteOptions(null); setRouteChoice(0); setRouteError(''); return;
    }
    let cancelled = false;
    setRouteOptions(null); setRouteError('');
    api.caravanRoutes(originCastle, targetCastle).then(res => {
      if (cancelled) return;
      const routes = res.routes || [];
      setRouteOptions(routes);
      const firstAvailable = routes.findIndex(r => r.available !== false);
      setRouteChoice(firstAvailable >= 0 ? firstAvailable : 0);
    }).catch(e => {
      if (!cancelled) { setRouteOptions([]); setRouteError(e.message || 'مسیری پیدا نشد'); }
    });
    return () => { cancelled = true; };
  }, [target, originCastle, targetCastle]);

  const [market, setMarket] = useState(null);
  const [buyQty, setBuyQty] = useState({});
  const [buyBusy, setBuyBusy] = useState(null);
  const [playerMarket, setPlayerMarket] = useState(null);
  const [sellResource, setSellResource] = useState(CARAVAN_GOODS.find(g => g !== 'gold'));
  const [sellQty, setSellQty] = useState(1);
  const [playerBuyQty, setPlayerBuyQty] = useState({});
  const [playerMarketBusy, setPlayerMarketBusy] = useState(null);

  const [black, setBlack] = useState(null);
  const [blackQty, setBlackQty] = useState({});
  const [blackBusy, setBlackBusy] = useState(null);

  const loadAlliances = () => api.caravanPartners().then(setAlliances).catch(e => toast(e.message));
  const loadCaravans = () => api.myCaravans().then(setCaravans).catch(e => toast(e.message));
  const loadMarket = () => api.market().then(setMarket).catch(e => toast(e.message));
  const loadPlayerMarket = () => api.playerMarket().then(setPlayerMarket).catch(e => toast(e.message));
  const loadBlack = () => api.blackMarket().then(setBlack).catch(e => toast(e.message));

  useEffect(() => { loadAlliances(); loadCaravans(); loadMarket(); loadPlayerMarket(); loadBlack(); }, []);
  useEffect(() => {
    if (tab !== 'market') return;
    const timer = setInterval(() => { loadMarket(); loadPlayerMarket(); loadBlack(); }, 30000);
    return () => clearInterval(timer);
  }, [tab]);

  const sellToPlayerMarket = async () => {
    setPlayerMarketBusy('sell');
    try {
      await api.playerMarketSell(sellResource, Number(sellQty), Number(sellPrice));
      haptic('medium'); toast(`${fa(sellQty)} واحد کالا، هر واحد ${fa(sellPrice)} سکه برای فروش ثبت شد`);
      api.me().then(setMe); loadPlayerMarket();
    } catch (e) { toast(e.message); }
    setPlayerMarketBusy(null);
  };

  const buyFromPlayer = async (listing) => {
    const qty = Math.max(1, Math.min(listing.qty, Number(playerBuyQty[listing.id]) || 1));
    setPlayerMarketBusy(listing.id);
    try {
      await api.playerMarketBuy(listing.id, qty); haptic('medium');
      toast(`${fa(qty)} واحد خریدی؛ ${fa(qty * listing.price)} سکه پرداخت شد`);
      api.me().then(setMe); loadPlayerMarket();
    } catch (e) { toast(e.message); }
    setPlayerMarketBusy(null);
  };

  const cancelPlayerSale = async (listing) => {
    setPlayerMarketBusy(listing.id);
    try { await api.playerMarketCancel(listing.id); toast('آگهی برداشته شد و باقی کالا برگشت'); api.me().then(setMe); loadPlayerMarket(); }
    catch (e) { toast(e.message); }
    setPlayerMarketBusy(null);
  };

  const partners = (alliances || []).filter(a =>
    a.status === 'accepted' && (a.type === 'trade' || a.type === 'full_alliance'));
  useEffect(() => {
    if (tab !== 'caravan') return;
    const timer = setInterval(loadAlliances, 15000);
    return () => clearInterval(timer);
  }, [tab]);
  const totalGoods = Object.values(amounts).reduce((s, v) => s + (v || 0), 0);

  const sendCaravan = async () => {
    if (!target) { toast('یک هم‌پیمان تجاری را انتخاب کن'); return; }
    const resources = Object.fromEntries(Object.entries(amounts).filter(([, v]) => v > 0));
    if (!Object.keys(resources).length) { toast('حداقل یک کالا انتخاب کن'); return; }
    const selectedRoute = routeOptions?.[routeChoice];
    if (!selectedRoute || selectedRoute.available === false) { toast('یک مسیر تجاری مجاز انتخاب کن'); return; }
    setSendBusy(true);
    try {
      const res = await api.sendCaravan({
        target_tg_id: Number(target), resources,
        origin_castle: originCastle, target_castle: targetCastle || undefined,
        via: selectedRoute.path,
      });
      haptic('medium');
      api.me().then(setMe);
      toast(`کاروان فرستاده شد — حدود ${res.travel_minutes.toLocaleString('fa-IR')} دقیقه تا رسیدن`);
      setAmounts(emptyAmounts()); setTarget(''); setOriginCastle(me.castle);
      loadCaravans();
    } catch (e) { toast(e.message); }
    setSendBusy(false);
  };

  const buyMarket = async (resource) => {
    const qty = Number(buyQty[resource] || 1);
    setBuyBusy(resource);
    try {
      await api.marketBuy(resource, qty, market.find(m => m.resource === resource)?.price);
      haptic('medium');
      api.me().then(setMe);
      toast(`${qty.toLocaleString('fa-IR')} واحد ${TRADE_GOOD_NAMES[resource] || resource} خریداری شد`);
      loadMarket();
    } catch (e) { toast(e.message); loadMarket(); }
    setBuyBusy(null);
  };

  const buyBlack = async (m) => {
    const qty = Number(blackQty[m.id] || 1);
    setBlackBusy(m.id);
    try {
      await api.blackMarketBuy(m.id, qty);
      haptic('medium');
      api.me().then(setMe);
      toast(`${qty.toLocaleString('fa-IR')} واحد ${m.name} از بازار سیاه خریداری شد`);
      loadBlack();
    } catch (e) { toast(e.message); }
    setBlackBusy(null);
  };

  return (
    <section className="trade-page">
      <header className="trade-hero"><div><span className="trade-eyebrow">خزانه و بازرگانی</span><h1 className="page-title">تجارت و سرمایه</h1></div><div className="trade-wallet"><Coin s={18} /><strong>{fa(me.resources?.gold)}</strong><small>سکه</small></div></header>
      <p className="page-sub trade-intro">کالا مبادله کن، کاروان بفرست و در آیندهٔ قلمرو سرمایه‌گذاری کن.</p>
      <nav className="trade-nav" role="tablist" aria-label="بخش‌های تجارت">
        {TABS.map(t => { const Icon = t.icon; return <button type="button" key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? 'selected' : ''} onClick={() => { haptic(); setTab(t.key); }}><Icon s={22} /><strong>{t.label}</strong><small>{t.detail}</small></button>; })}
      </nav>
      {tab === 'market' && <nav className="exchange-tabs" aria-label="نوع بازار">{[['official','بازار رسمی'],['players','بازار بازیکنان'],['black','بلک‌مارکت']].map(([key,label]) => <button key={key} type="button" aria-pressed={marketSection === key} className={marketSection === key ? 'selected' : ''} onClick={() => { setMarketSection(key); loadMarket(); loadPlayerMarket(); loadBlack(); }}>{label}</button>)}</nav>}
      {tab === 'market' && <div className="exchange-refresh"><small>قیمت هر واحد به سکه است</small><button type="button" onClick={() => { loadMarket(); loadPlayerMarket(); loadBlack(); }}>تازه‌سازی بازار</button></div>}
      {tab === 'market' && (marketSection === 'official' ? market : marketSection === 'players' ? playerMarket : black) === null && <div className="exchange-empty" role="status">در حال دریافت کالاها…</div>}

      {tab === 'projects' && <Projects />}
      {tab === 'caravan' && (
        <>
          <div className="sect up u2">فرستادن کاروان</div>
          <div className="card up u2">
            {partners.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
                هنوز هیچ پیمان تجاری یا اتحاد کاملی نبستی — اول از دیپلماسی یکی برقرار کن
              </div>
            ) : (
              <>
                <label className="f" style={{ marginTop: 0 }}>هم‌پیمان تجاری</label>
                <select value={target} onChange={e => setTarget(e.target.value)}>
                  <option value="">— انتخاب کن —</option>
                  {partners.map(p => <option key={p.other_id} value={p.other_id}>{p.other_name} · {p.type_name}</option>)}
                </select>
                {myCastles.length > 1 && (
                  <>
                    <label className="f">از کدوم قلعه‌ات</label>
                    <select value={originCastle} onChange={e => setOriginCastle(e.target.value)}>
                      {myCastles.map(c => <option key={c} value={c}>{castleLabel(c)}{c === me.castle ? ' (خانه)' : ''}</option>)}
                    </select>
                  </>
                )}
                {target && targetCastles.length > 1 && (
                  <>
                    <label className="f">به کدوم قلعهٔ او</label>
                    <select value={targetCastle} onChange={e => setTargetCastle(e.target.value)}>
                      {targetCastles.map(c => <option key={c} value={c}>{castleLabel(c)}</option>)}
                    </select>
                  </>
                )}
                {target && targetCastle && (
                  routeOptions === null ? (
                    <div className="page-sub" style={{ margin: '10px 4px 0' }}>در حال بررسی مسیرهای تجاری...</div>
                  ) : routeOptions.length ? (
                    <div style={{ marginTop: 12 }}>
                      <label className="f" style={{ marginTop: 0 }}>مسیر کاروان — یکی را انتخاب کن</label>
                      {routeOptions.map((route, index) => {
                        const unavailable = route.available === false;
                        const missing = (route.missing_lords || []).map(lord => lord.name).join('، ');
                        return <div key={index}
                          onClick={() => { if (!unavailable) { haptic(); setRouteChoice(index); } }}
                          className={`pick ${routeChoice === index && !unavailable ? 'sel' : ''}`}
                          style={{ marginBottom: 7, textAlign: 'right', cursor: unavailable ? 'not-allowed' : 'pointer', opacity: unavailable ? .58 : 1 }}>
                          <div className="n" style={{ fontSize: 11.5, lineHeight: 1.9 }}>
                            {route.path.map(castleLabel).join('  ←  ')}
                          </div>
                          <div className="c">
                            {route.minutes.toLocaleString('fa-IR')} دقیقه{route.via_sea ? ' · ⚓ مسیر دریایی' : ''}
                          </div>
                          {unavailable && <div style={{ color: 'var(--danger)', fontSize: 11, marginTop: 5 }}>
                            این مسیر بسته است؛ با {missing || 'لردهای مسیر'} پیمان تجاری یا اتحاد کامل نداری.
                          </div>}
                        </div>;
                      })}
                      <div className="page-sub" style={{ margin: '8px 4px 0' }}>
                        پیمان عدم تجاوز برای عبور کاروان کافی نیست؛ تمام لردهای مسیر باید پیمان تجاری یا اتحاد کامل داشته باشند.
                      </div>
                    </div>
                  ) : <div className="page-sub" style={{ margin: '10px 4px 0', color: 'var(--danger)' }}>
                    {routeError || 'هیچ مسیر تجاری تا این قلعه پیدا نشد.'}
                  </div>
                )}
                <label className="f">کالاها</label>
                {CARAVAN_GOODS.map(g => {
                  const Icon = RES_ICON[g];
                  return (
                    <div className="troop" key={g}>
                      <div className="tn">
                        {Icon && <Icon s={14} />} {TRADE_GOOD_NAMES[g]}
                        <small>{(me.resources[g] ?? 0).toLocaleString('fa-IR')} موجودی</small>
                      </div>
                      <input type="number" min="0" max={me.resources[g] ?? 0} value={amounts[g]}
                             onChange={e => setAmounts({ ...amounts, [g]: Math.max(0, Math.min(me.resources[g] ?? 0, +e.target.value || 0)) })} />
                    </div>
                  );
                })}
                <button className="btn" style={{ marginTop: 14 }}
                  disabled={sendBusy || !totalGoods || !routeOptions?.[routeChoice] || routeOptions[routeChoice].available === false}
                  onClick={sendCaravan}>
                  {sendBusy ? 'در حال ارسال...' : 'مُهر و فرستادن کاروان'}
                </button>
              </>
            )}
          </div>

          <div className="sect up u3">کاروان‌ها</div>
          <div className="up u3">
            {(!caravans || caravans.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز کاروانی رد و بدل نشده</div>
            )}
            {caravans && caravans.map(c => (
              <div className={`warband ${c.mine_sent ? 'mine' : ''}`} key={c.id}>
                <div className="wi"><Send s={16} /></div>
                <div className="t">
                  {c.mine_sent
                    ? <><b>کاروانت</b> به‌سوی <b>{c.to}</b> ({c.to_castle})</>
                    : <><b>کاروانی از {c.from}</b> ({c.from_castle}) به‌سویت</>}
                  <div className="tm">
                    {Object.entries(c.resources).map(([k, v]) => `${v.toLocaleString('fa-IR')} ${k}`).join(' · ')}
                    {' · '}{c.delivery_failed ? 'تحویل ناموفق — گیرنده دیگر فعال نیست' : c.arrived ? 'رسیده' : `در راه — حدود ${c.travel_minutes.toLocaleString('fa-IR')} دقیقه`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'market' && marketSection === 'players' && <>
        <div className="exchange-heading"><span className="trade-eyebrow">بازار بازیکنان</span><h2>قیمت را فروشنده تعیین می‌کند</h2><p>حداقل هر واحد یک سکه؛ کم شدن موجودی، قیمت آگهی را تغییر نمی‌دهد.</p></div>
        <details className="exchange-sell"><summary>＋ فروش کالای من</summary><form onSubmit={e => { e.preventDefault(); sellToPlayerMarket(); }}>
          <label>نوع کالا<select value={sellResource} onChange={e => setSellResource(e.target.value)}>{CARAVAN_GOODS.filter(g => g !== 'gold').map(g => <option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}</select></label>
          <div className="exchange-fields"><label>تعداد برای فروش<input type="number" inputMode="numeric" min="1" max={Math.floor(me.resources?.[sellResource] || 0)} step="1" required value={sellQty} onChange={e => setSellQty(e.target.value)} /></label><label>قیمت هر واحد (سکه)<input type="number" inputMode="numeric" min="1" max="1000000000" step="1" required value={sellPrice} onChange={e => setSellPrice(e.target.value)} /></label></div>
          <div className="exchange-preview"><span>دریافتی در صورت فروش کامل</span><strong>{fa(sellQty * sellPrice)} سکه</strong></div>
          <p className="exchange-note">{fa(me.resources?.[sellResource])} واحد در خزانه داری. کالای آگهی رزرو می‌شود؛ با برداشتن آگهی، باقی‌مانده برمی‌گردد.</p>
          <button className="btn" disabled={playerMarketBusy === 'sell'}>ثبت آگهی فروش</button>
        </form></details>
        <div className="exchange-grid">{playerMarket?.map(m => <MarketCard key={m.id} item={m} kind="player" value={playerBuyQty[m.id]} onQuantity={q => setPlayerBuyQty(v => ({...v,[m.id]:q}))} onBuy={() => buyFromPlayer(m)} onCancel={() => cancelPlayerSale(m)} busy={playerMarketBusy === m.id} />)}</div>
        {playerMarket?.length === 0 && <div className="exchange-empty">هنوز کالایی برای فروش ثبت نشده.<small>نخستین آگهی را از «فروش کالای من» بساز.</small></div>}
      </>}
      {tab === 'market' && marketSection === 'official' && <>
        <div className="exchange-heading"><span className="trade-eyebrow">بازار رسمی وستروس</span><h2>قیمت تابع موجودی بازار است</h2><p>با کمبود کالا قیمت به‌تدریج بالا می‌رود؛ تأمین دوباره، قیمت را به پایه نزدیک می‌کند.</p></div>
        <div className="exchange-grid">{market?.map(m => <MarketCard key={m.resource} item={m} kind="official" value={buyQty[m.resource]} onQuantity={q => setBuyQty(v => ({...v,[m.resource]:q}))} onBuy={() => buyMarket(m.resource)} busy={buyBusy === m.resource} />)}</div>
        {market?.length === 0 && <div className="exchange-empty">عرضهٔ رسمی فعلاً تمام شده است.<small>برای خرید از بازیکنان، بازار بازیکنان را ببین.</small></div>}
        <details className="exchange-guide"><summary>قیمت و درصد تغییر چگونه حساب می‌شوند؟</summary><p>قیمت پایه و حجم مرجع را عرضهٔ ادمین مشخص می‌کند. قیمت با کاهش موجودی تا حداکثر دو برابر پایه بالا می‌رود و به سکهٔ کامل گرد می‌شود؛ بنابراین با هر یک واحد خرید الزاماً تغییر نمی‌کند. درصد کنار کالا نسبت به پایه است، نه نسبت به خرید قبلی. مبلغ همین سفارش با قیمت نمایش‌داده‌شده محاسبه می‌شود.</p></details>
      </>}
      {tab === 'market' && marketSection === 'black' && <>
        <div className="exchange-heading black-heading"><span className="trade-eyebrow">بازار سیاه</span><h2>فرصت محدود، قیمت ثابت</h2><p>قیمت هر عرضه تا پایان مهلت ثابت است؛ فقط موجودی و زمان باقی‌مانده کاهش پیدا می‌کنند.</p></div>
        <div className="exchange-grid">{black?.map(m => <MarketCard key={m.id} item={m} kind="black" value={blackQty[m.id]} onQuantity={q => setBlackQty(v => ({...v,[m.id]:q}))} onBuy={() => buyBlack(m)} busy={blackBusy === m.id} />)}</div>
        {black?.length === 0 && <div className="exchange-empty">فعلاً عرضه‌ای در بازار سیاه نیست.<small>کالاهای تازه پس از ثبت ادمین اینجا ظاهر می‌شوند.</small></div>}
      </>}
    </section>
  );
}
