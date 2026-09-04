import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Wood, Rock, Pick, Wheat, Wine, Send } from '../components/Icons.jsx';
import { CARAVAN_GOODS, TRADE_GOOD_NAMES, castleLabel } from '../gamedata.js';

const RES_ICON = { gold: Coin, wood: Wood, stone: Rock, iron: Pick, food: Wheat, wine: Wine };

const TABS = [
  { key: 'caravan', label: 'کاروان' },
  { key: 'market',  label: 'بازار وستروس' },
  { key: 'black',   label: 'بازار سیاه' },
];

const emptyAmounts = () => Object.fromEntries(CARAVAN_GOODS.map(g => [g, 0]));

export default function Trade() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState('caravan');

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

  const loadAlliances = () => api.diplomacyMine().then(setAlliances).catch(e => toast(e.message));
  const loadCaravans = () => api.myCaravans().then(setCaravans).catch(e => toast(e.message));
  const loadMarket = () => api.market().then(setMarket).catch(e => toast(e.message));
  const loadPlayerMarket = () => api.playerMarket().then(setPlayerMarket).catch(e => toast(e.message));
  const loadBlack = () => api.blackMarket().then(setBlack).catch(e => toast(e.message));

  useEffect(() => { loadAlliances(); loadCaravans(); loadMarket(); loadPlayerMarket(); loadBlack(); }, []);

  const sellToPlayerMarket = async () => {
    setPlayerMarketBusy('sell');
    try {
      await api.playerMarketSell(sellResource, Math.max(1, Number(sellQty) || 1));
      haptic('medium'); toast('کالا با قیمت ثابت هر واحد یک سکه برای فروش گذاشته شد');
      api.me().then(setMe); loadPlayerMarket();
    } catch (e) { toast(e.message); }
    setPlayerMarketBusy(null);
  };

  const buyFromPlayer = async (listing) => {
    const qty = Math.max(1, Math.min(listing.qty, Number(playerBuyQty[listing.id]) || 1));
    setPlayerMarketBusy(listing.id);
    try {
      await api.playerMarketBuy(listing.id, qty); haptic('medium');
      toast(`${qty.toLocaleString('fa-IR')} واحد خریدی؛ ${qty.toLocaleString('fa-IR')} سکه پرداخت شد`);
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
    const qty = buyQty[resource] || 1;
    setBuyBusy(resource);
    try {
      await api.marketBuy(resource, qty);
      haptic('medium');
      api.me().then(setMe);
      toast(`${qty.toLocaleString('fa-IR')} واحد ${TRADE_GOOD_NAMES[resource] || resource} خریداری شد`);
      loadMarket();
    } catch (e) { toast(e.message); }
    setBuyBusy(null);
  };

  const buyBlack = async (m) => {
    const qty = blackQty[m.id] || 1;
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
    <>
      <div className="page-title up">تجارت</div>
      <div className="page-sub up">کاروان بفرست، از بازار وستروس خرید کن، یا شانست رو تو بازار سیاه امتحان کن</div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.key); }}>{t.label}</button>
        ))}
      </div>

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
                    {' · '}{c.arrived ? 'رسیده' : `در راه — حدود ${c.travel_minutes.toLocaleString('fa-IR')} دقیقه`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'market' && (
        <>
          <div className="sect up u2">بازار وستروس</div>
          <div className="page-sub up u2" style={{ marginTop: -6 }}>بازار رسمی قیمت شناور دارد؛ در بازار لردها هر واحد کالا دقیقاً یک سکه است.</div>
          <div className="card up u2" style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 800, marginBottom: 8 }}>فروش کالای خودت</div>
            <div className="grid2">
              <select value={sellResource} onChange={e => setSellResource(e.target.value)}>
                {CARAVAN_GOODS.filter(g => g !== 'gold').map(g => <option key={g} value={g}>{TRADE_GOOD_NAMES[g]}</option>)}
              </select>
              <input type="number" min="1" value={sellQty} onChange={e => setSellQty(Math.max(1, Number(e.target.value) || 1))} />
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--mid)', marginTop: 8 }}>قیمت قابل تغییر نیست: هر واحد ۱ سکه. کالا تا زمان فروش یا برداشتن آگهی از موجودی‌ات خارج می‌شود.</div>
            <button className="btn ghost" style={{ marginTop: 10 }} disabled={playerMarketBusy === 'sell'} onClick={sellToPlayerMarket}>ثبت برای فروش</button>
          </div>
          <div className="sect up u2">آگهی لردها</div>
          <div className="up u2">
            {(!playerMarket || playerMarket.length === 0) && <div className="card" style={{ textAlign: 'center', color: 'var(--mid)' }}>فعلاً آگهی بازیکنی وجود ندارد</div>}
            {(playerMarket || []).map(m => <div className="card market-row" key={m.id}>
              <div className="res"><div className="n">{m.name}<small>فروشنده: {m.seller_name} · {m.qty.toLocaleString('fa-IR')} واحد</small></div><div className="val">۱ <Coin s={12} /></div></div>
              {m.mine ? <button className="btn ghost" disabled={playerMarketBusy === m.id} onClick={() => cancelPlayerSale(m)}>برداشتن آگهی</button> : <div className="buy-row">
                <input type="number" min="1" max={m.qty} value={playerBuyQty[m.id] || 1} onChange={e => setPlayerBuyQty({ ...playerBuyQty, [m.id]: Math.max(1, Math.min(m.qty, Number(e.target.value) || 1)) })} />
                <button className="btn ghost" disabled={playerMarketBusy === m.id} onClick={() => buyFromPlayer(m)}>خرید</button>
              </div>}
            </div>)}
          </div>
          <div className="sect up u2">بازار رسمی</div>
          <div className="up u2">
            {(!market || market.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>فعلاً کالایی در بازار نیست</div>
            )}
            {market && market.map(m => {
              const Icon = RES_ICON[m.resource];
              const up = m.change_pct > 0, down = m.change_pct < 0;
              const qty = buyQty[m.resource] || 1;
              return (
                <div className="card market-row" key={m.resource}>
                  <div className="res">
                    <div className="ic">{Icon && <Icon s={18} />}</div>
                    <div className="n">{m.name}<small>{m.qty.toLocaleString('fa-IR')} واحد موجود</small></div>
                    <div className="val">
                      {m.price.toLocaleString('fa-IR')} <Coin s={12} />
                      <span className={`chg ${up ? 'up' : down ? 'down' : ''}`}>
                        {up ? '▲' : down ? '▼' : '–'}{Math.abs(m.change_pct).toLocaleString('fa-IR')}٪
                      </span>
                    </div>
                  </div>
                  <div className="buy-row">
                    <input type="number" min="1" max={m.qty} value={qty}
                           onChange={e => setBuyQty({ ...buyQty, [m.resource]: Math.max(1, Math.min(m.qty, +e.target.value || 1)) })} />
                    <button className="btn ghost" disabled={buyBusy === m.resource} onClick={() => buyMarket(m.resource)}>
                      {buyBusy === m.resource ? '...' : `خرید (${(qty * m.price).toLocaleString('fa-IR')} طلا)`}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {tab === 'black' && (
        <>
          <div className="sect up u2">بازار سیاه</div>
          <div className="page-sub up u2" style={{ marginTop: -6 }}>کالای محدود، زمان محدود — قبل از تمومش خریدار باش</div>
          <div className="up u2">
            {(!black || black.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>فعلاً جنسی توی بازار سیاه نیست</div>
            )}
            {black && black.map(m => {
              const Icon = RES_ICON[m.resource];
              const h = Math.floor(m.expires_in_minutes / 60), mm = m.expires_in_minutes % 60;
              const qty = blackQty[m.id] || 1;
              return (
                <div className="card market-row black" key={m.id}>
                  <div className="res">
                    <div className="ic">{Icon && <Icon s={18} />}</div>
                    <div className="n">{m.name}<small>فقط {m.qty.toLocaleString('fa-IR')} واحد باقی مانده</small></div>
                    <div className="val">
                      {m.price.toLocaleString('fa-IR')} <Coin s={12} />
                      <span className="chg countdown">⏳ {h > 0 ? `${h.toLocaleString('fa-IR')}س ` : ''}{mm.toLocaleString('fa-IR')}د</span>
                    </div>
                  </div>
                  <div className="buy-row">
                    <input type="number" min="1" max={m.qty} value={qty}
                           onChange={e => setBlackQty({ ...blackQty, [m.id]: Math.max(1, Math.min(m.qty, +e.target.value || 1)) })} />
                    <button className="btn ghost" disabled={blackBusy === m.id} onClick={() => buyBlack(m)}>
                      {blackBusy === m.id ? '...' : `خرید (${(qty * m.price).toLocaleString('fa-IR')} طلا)`}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
