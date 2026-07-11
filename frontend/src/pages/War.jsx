import { useEffect, useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Swords } from '../components/Icons.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import {
  COMMON_TROOPS, SPECIAL_COST, REGIONS_STATIC, OP_TYPES,
  TROOP_UNIT_BUILDINGS, FOOD_COST_REGULAR, FOOD_COST_SPECIAL, travelMinutes,
} from '../gamedata.js';

export default function War() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const men = me.resources.men ?? 0;
  const specials = REGIONS_STATIC[me.region]?.special || [];

  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [buildings, setBuildings] = useState(null);
  const [mine, setMine] = useState(null);

  const loadMap = () => {
    setMapError(false);
    api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); });
  };
  const loadBuildings = () => api.buildings().then(setBuildings).catch(e => { toast(e.message); setBuildings([]); });
  const loadMine = () => api.warMine().then(setMine).catch(e => { toast(e.message); setMine([]); });

  useEffect(() => { loadMap(); loadBuildings(); loadMine(); }, []);

  const builtLevels = useMemo(() => {
    const m = {};
    (buildings || []).forEach(b => { m[b.id] = b.level; });
    return m;
  }, [buildings]);

  const allTroops = [
    ...COMMON_TROOPS.map(t => ({ ...t, special: false })),
    ...specials.map(n => ({ id: n, name: n, cost: SPECIAL_COST, special: true })),
  ];

  const stationedOrigins = useMemo(
    () => (mine || []).filter(c => c.active && c.op_type === 'garrison').map(c => c.target),
    [mine]
  );
  const originOptions = [me.castle, ...stationedOrigins.filter(o => o !== me.castle)];

  const [origin, setOrigin] = useState(me.castle);
  const [opType, setOpType] = useState(OP_TYPES[0].id);
  const [target, setTarget] = useState(null); // { name, region, ... } | null
  const [plan, setPlan] = useState('');
  const [counts, setCounts] = useState(Object.fromEntries(allTroops.map(t => [t.id, 0])));
  const [busy, setBusy] = useState(false);

  const op = OP_TYPES.find(o => o.id === opType);

  const findCastleRegion = (name) => {
    if (!mapData) return me.region;
    for (const r of mapData.regions) {
      if (r.castles.some(c => c.name === name)) return r.id;
    }
    return me.region;
  };

  const sameCastle = !op.needsTarget || (target && target.name === origin);
  const originRegion = findCastleRegion(origin);
  const targetRegion = op.needsTarget && target ? (target.region || findCastleRegion(target.name)) : originRegion;
  const eta = travelMinutes(sameCastle, originRegion, targetRegion);

  const unlocked = (troop) => {
    if (troop.special) return true;
    const req = TROOP_UNIT_BUILDINGS[troop.id];
    if (!req) return true;
    return (builtLevels[req.camp] > 0) && (builtLevels[req.armory] > 0);
  };

  const goldCost = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * t.cost, 0),
    [counts]
  );
  const menCommitted = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0), 0),
    [counts]
  );
  const foodPerDay = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * (t.special ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR), 0),
    [counts]
  );
  const overGold = goldCost > gold;
  const overMen = menCommitted > men;

  const resetForm = () => {
    setPlan(''); setTarget(null);
    setCounts(Object.fromEntries(allTroops.map(t => [t.id, 0])));
  };

  const send = async () => {
    if (op.needsTarget && !target) { toast('مقصد را از روی نقشه یا لیست انتخاب کن'); return; }
    if (op.needsTarget && opType !== 'garrison' && plan.trim().length < 50) {
      toast('سناریو خیلی کوتاه است — نقشه‌ات را شرح بده'); return;
    }
    if (menCommitted <= 0) { toast('هیچ نیرویی گسیل نکرده‌ای'); return; }
    if (overGold) { toast('خزانه کافی نیست'); return; }
    if (overMen) { toast('نفرات کافی نداری'); return; }
    setBusy(true);
    try {
      await api.submitCampaign({
        origin_castle: origin, op_type: opType,
        target_castle: op.needsTarget ? target.name : null,
        plan: plan.trim(), troops: counts,
      });
      haptic('medium');
      setMe({
        ...me,
        resources: { ...me.resources, gold: gold - goldCost, men: men - menCommitted },
        active_campaigns: (me.active_campaigns ?? 0) + 1,
      });
      toast(eta > 0 ? `فرمان مُهر شد — لشکر تا ${eta.toLocaleString('fa-IR')} دقیقه دیگر می‌رسد` : 'فرمان مُهر شد — لشکر همین‌جاست');
      resetForm();
      loadMine(); loadMap();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  const cancelCampaign = async (c) => {
    try {
      await api.cancelCampaign(c.id);
      haptic('medium');
      setMe({
        ...me,
        resources: { ...me.resources, men: men + c.men_committed },
        active_campaigns: Math.max(0, (me.active_campaigns ?? 0) - 1),
      });
      toast('لشکر لغو شد و نفراتش به خانه برگشتند');
      loadMine(); loadMap();
    } catch (e) { toast(e.message); }
  };

  if (mapError) return (
    <>
      <div className="page-title up">نیروها/لشکرکشی</div>
      <div className="card up u1" style={{ textAlign: 'center', color: 'var(--mid)' }}>
        نقشه بارگذاری نشد — اتصال به سرور را بررسی کن
        <div style={{ marginTop: 12 }}>
          <button className="btn ghost" style={{ padding: 11 }} onClick={loadMap}>تلاش دوباره</button>
        </div>
      </div>
    </>
  );
  if (!mapData || !buildings || !mine) return <div className="loading">نیروها در راه‌اند...</div>;

  return (
    <>
      <div className="page-title up">نیروها/لشکرکشی</div>
      <div className="page-sub up">روی یک قلعه در نقشه کلیک کن تا اطلاعاتش را ببینی یا آن را هدف بگیری</div>

      <div className="sect up u1">نقشهٔ وستروس</div>
      <div className="up u1">
        <WesterosMap data={mapData} meCastle={me.castle} onSelectTarget={(c) => { haptic(); setTarget(c); toast(`${c.name} به‌عنوان مقصد انتخاب شد`); }} />
      </div>

      <div className="sect up u2">لشکرهای در حرکت</div>
      <div className="up u2">
        {mapData.campaigns.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
            هیچ لشکری در حرکت نیست — وستروس در آرامشی مشکوک است
          </div>
        )}
        {mapData.campaigns.map((c, i) => {
          const cSameCastle = c.from === c.to;
          return (
            <div key={i} className={`warband ${c.mine ? 'mine' : ''}`}>
              <div className="wi"><Swords s={17} /></div>
              <div className="t">
                {cSameCastle
                  ? <><b>لشکر {c.from}</b> در حال دفاع از قلعه است</>
                  : <><b>لشکری از {c.from}</b> به‌سوی <b>{c.to}</b> در حرکت است</>}
                <div className="tm">
                  {c.mine ? 'فرمان تو' : `آشکار شده — ${Math.max(0, c.revealed_minutes_ago).toLocaleString('fa-IR')} دقیقه پیش`}
                  {' · '}{c.arrived ? 'به مقصد رسیده' : `در راه — حدود ${c.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر`}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="sect up u3">فرمان لشکرکشی</div>
      <div className="card up u3">
        <label className="f" style={{ marginTop: 0 }}>مبدا</label>
        <select value={origin} onChange={e => setOrigin(e.target.value)}>
          {originOptions.map(o => <option key={o} value={o}>{o}{o === me.castle ? ' (قلعهٔ خودت)' : ' (لشکر مستقر)'}</option>)}
        </select>

        <label className="f">نوع عملیات</label>
        <select value={opType} onChange={e => { setOpType(e.target.value); setTarget(null); }}>
          {OP_TYPES.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>

        {op.needsTarget ? (
          <>
            <label className="f">مقصد</label>
            <div className="target-pick">
              {target ? (
                <>
                  <span>{target.name}</span>
                  <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11.5 }} onClick={() => setTarget(null)}>پاک‌کردن</button>
                </>
              ) : <span style={{ color: 'var(--mid)' }}>از روی نقشه در بالا انتخاب کن</span>}
            </div>
          </>
        ) : (
          <div className="page-sub" style={{ margin: '10px 4px 0' }}>عملیات دفاعی برای قلعهٔ مبدا — نیازی به مقصد نیست</div>
        )}

        <div className="page-sub" style={{ margin: '10px 4px 0' }}>
          زمان رسیدن لشکر: <b style={{ color: 'var(--az2)' }}>{eta > 0 ? `حدود ${eta.toLocaleString('fa-IR')} دقیقه` : 'بی‌درنگ — همین‌جاست'}</b>
        </div>

        {op.needsTarget && opType !== 'garrison' && (
          <>
            <label className="f">سناریوی نبرد — تا دو صفحه</label>
            <textarea value={plan} onChange={e => setPlan(e.target.value)}
                      placeholder="مسیر لشکر، آرایش جنگی، نیرنگ‌ها..." />
          </>
        )}
      </div>

      <div className="sect up u3">گسیل نیرو</div>
      <div className="card up u3">
        {allTroops.map(t => {
          const ok = unlocked(t);
          const req = !t.special && TROOP_UNIT_BUILDINGS[t.id];
          return (
            <div className="troop" key={t.id}>
              <div className="tn">
                {t.name}
                <small style={t.special ? { color: 'var(--az2)' } : {}}>
                  {t.special ? 'نیروی ویژهٔ اقلیم تو · ' : ''}
                  {t.cost.toLocaleString('fa-IR')} طلا/نفر · {(t.special ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR).toLocaleString('fa-IR')} غله/روز
                  {!ok && req ? ' · نیاز به پادگان و کارگاه تسلیحاتِ این یگان' : ''}
                </small>
              </div>
              <input type="number" min="0" value={counts[t.id]} disabled={!ok}
                     onChange={e => setCounts({ ...counts, [t.id]: Math.max(0, +e.target.value || 0) })} />
            </div>
          );
        })}
        <div className={`cost ${overGold || overMen ? 'over' : ''}`}>
          <span>هزینهٔ طلا / نفرات / آذوقهٔ روزانه</span>
          <b>{goldCost.toLocaleString('fa-IR')} طلا · {menCommitted.toLocaleString('fa-IR')}/{men.toLocaleString('fa-IR')} نفر · {foodPerDay.toLocaleString('fa-IR')} غله/روز</b>
        </div>
      </div>

      <div className="up u3">
        <button className="btn" disabled={overGold || overMen || busy} onClick={send}>
          {overGold ? 'خزانه کافی نیست' : overMen ? 'نفرات کافی نیست' : busy ? 'در حال ارسال...' : 'مُهر و ارسال فرمان'}
        </button>
      </div>

      <div className="sect up u4">لشکرهای من</div>
      <div className="up u4">
        {mine.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز لشکری نفرستاده‌ای</div>
        )}
        {mine.map(c => (
          <div className="card" key={c.id} style={{ marginBottom: 10 }}>
            <div className="res">
              <div className="ic"><Swords s={16} /></div>
              <div className="n">
                {c.op_name}<small>{c.origin} ← {c.target} · {c.men_committed.toLocaleString('fa-IR')} نفر · {c.food_per_day.toLocaleString('fa-IR')} غله/روز</small>
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--low)', margin: '8px 0' }}>
              {c.active
                ? (c.arrived ? 'رسیده به مقصد' : `در راه — حدود ${c.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر`)
                : 'لغوشده'}
              {c.active ? ` · ${c.days_active.toLocaleString('fa-IR')} روز فعال` : ''}
            </div>
            {c.active && (
              <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} onClick={() => cancelCampaign(c)}>لغو لشکر</button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
