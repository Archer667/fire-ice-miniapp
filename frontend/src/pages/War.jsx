import { useEffect, useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Swords, Coin, People, Wheat } from '../components/Icons.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import {
  COMMON_TROOPS, SPECIAL_COST, SPECIAL_POWER, REGIONS_STATIC, OP_TYPES,
  TROOP_UNIT_BUILDINGS, FOOD_COST_REGULAR, FOOD_COST_SPECIAL, travelMinutes, campaignPower,
  NAVAL_TROOP, NAVAL_CAMP_BUILDING, REPORT_DELAY_MINUTES,
} from '../gamedata.js';

const TABS = [
  { key: 'command', label: 'نقشه و فرمان' },
  { key: 'reports', label: 'گزارش‌ها' },
];
const SEEN_KEY = 'fireice_war_reports_seen';
const loadSeenIds = () => { try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY)) || []); } catch { return new Set(); } };

export default function War() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const men = me.resources.men ?? 0;
  const specials = REGIONS_STATIC[me.region]?.special || [];

  const [tab, setTab] = useState('command');
  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [buildings, setBuildings] = useState(null);
  const [mine, setMine] = useState(null);
  const [seenIds, setSeenIds] = useState(loadSeenIds);

  const loadMap = () => {
    setMapError(false);
    api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); });
  };
  const loadBuildings = () => api.buildings().then(setBuildings).catch(e => { toast(e.message); setBuildings([]); });
  const loadMine = () => api.warMine().then(setMine).catch(e => { toast(e.message); setMine([]); });

  useEffect(() => { loadMap(); loadBuildings(); loadMine(); }, []);

  // گزارش لشکرکشی تازه، ۳۰ دقیقه بعد از ارسال در تب «گزارش‌ها» ظاهر می‌شود
  const visibleReports = useMemo(
    () => (mine || []).filter(c => Date.now() - new Date(c.created_at).getTime() >= REPORT_DELAY_MINUTES * 60000),
    [mine]
  );

  const newReportsCount = useMemo(
    () => visibleReports.filter(c => c.arrived && !seenIds.has(c.id)).length,
    [visibleReports, seenIds]
  );

  const openReports = () => {
    setTab('reports');
    if (!visibleReports.length) return;
    const next = new Set(seenIds);
    visibleReports.forEach(c => { if (c.arrived) next.add(c.id); });
    setSeenIds(next);
    localStorage.setItem(SEEN_KEY, JSON.stringify([...next]));
  };

  const builtLevels = useMemo(() => {
    const m = {};
    (buildings || []).forEach(b => { m[b.id] = b.level; });
    return m;
  }, [buildings]);

  const allTroops = [
    ...COMMON_TROOPS.map(t => ({ ...t, special: false })),
    ...specials.map(n => ({ id: n, name: n, cost: SPECIAL_COST, special: true })),
    ...(me.is_port ? [{ ...NAVAL_TROOP, special: false, naval: true }] : []),
  ];

  const stationedOrigins = useMemo(
    () => (mine || []).filter(c => c.active && c.op_type === 'garrison').map(c => c.target),
    [mine]
  );
  const originOptions = [me.castle, ...stationedOrigins.filter(o => o !== me.castle)];

  const [origin, setOrigin] = useState(me.castle);
  const [opType, setOpType] = useState(OP_TYPES[0].id);
  const [target, setTarget] = useState(null); // { name, region, ... } | null
  const [name, setName] = useState('');
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
  const isPortCastle = (name) => {
    if (!mapData) return name === me.castle && me.is_port;
    for (const r of mapData.regions) {
      const c = r.castles.find(c => c.name === name);
      if (c) return !!c.port;
    }
    return false;
  };

  const sameCastle = !op.needsTarget || (target && target.name === origin);
  const originRegion = findCastleRegion(origin);
  const targetRegion = op.needsTarget && target ? (target.region || findCastleRegion(target.name)) : originRegion;
  const eta = travelMinutes(sameCastle, originRegion, targetRegion);
  const badOriginForNaval = op.portOnly && !isPortCastle(origin);

  const unlocked = (troop) => {
    if (troop.naval) return builtLevels[NAVAL_CAMP_BUILDING] > 0;
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
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * ((t.special || t.naval) ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR), 0),
    [counts]
  );
  const estPower = useMemo(() => campaignPower(counts, builtLevels), [counts, builtLevels]);
  const overGold = goldCost > gold;
  const overMen = menCommitted > men;
  const badPortTarget = op.portOnly && target && !target.port;
  const formIssue = overGold ? 'خزانه کافی نیست'
    : overMen ? 'نفرات کافی نیست'
    : (op.needsTarget && !target) ? 'مقصد را انتخاب کن'
    : badPortTarget ? 'مقصد باید بندر باشد'
    : badOriginForNaval ? 'مبدا باید بندر باشد'
    : menCommitted <= 0 ? 'نیرویی گسیل نکرده‌ای'
    : null;

  const resetForm = () => {
    setName(''); setTarget(null);
    setCounts(Object.fromEntries(allTroops.map(t => [t.id, 0])));
  };

  const send = async () => {
    if (op.needsTarget && !target) { toast('مقصد را از روی نقشه یا لیست انتخاب کن'); return; }
    if (op.portOnly && target && !target.port) { toast('غارت دریایی فقط علیه اهداف بندری ممکن است'); return; }
    if (badOriginForNaval) { toast('غارت دریایی فقط از قلعه/شهرهای بندری ممکن است'); return; }
    if (menCommitted <= 0) { toast('هیچ نیرویی گسیل نکرده‌ای'); return; }
    if (overGold) { toast('خزانه کافی نیست'); return; }
    if (overMen) { toast('نفرات کافی نداری'); return; }
    setBusy(true);
    try {
      await api.submitCampaign({
        origin_castle: origin, op_type: opType,
        target_castle: op.needsTarget ? target.name : null,
        name: name.trim(), troops: counts,
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
      const res = await api.cancelCampaign(c.id);
      haptic('medium');
      setMe({
        ...me,
        resources: { ...me.resources, men: men + (res.men_refunded ?? 0) },
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

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); if (t.key === 'reports') openReports(); else setTab(t.key); }}>
            {t.label}
            {t.key === 'reports' && newReportsCount > 0 && <span className="dot badge" />}
          </button>
        ))}
      </div>

      {tab === 'command' && (
        <>
          <div className="sect up u2">نقشهٔ وستروس</div>
          <div className="up u2">
            <WesterosMap data={mapData} meCastle={me.castle} onSelectTarget={(c) => { haptic(); setTarget(c); toast(`${c.name} به‌عنوان مقصد انتخاب شد`); }} />
          </div>

          <div className="sect up u3">فرمان لشکرکشی</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>نام لشکرکشی</label>
            <input value={name} onChange={e => setName(e.target.value)} maxLength={60} placeholder="مثلاً «یورش بامداد» — اختیاری" />

            <label className="f">مبدا</label>
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
                {op.portOnly && target && !target.port && (
                  <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>
                    {target.name} بندر نیست — غارت دریایی فقط علیه اهداف بندری ممکن است
                  </div>
                )}
                {op.portOnly && badOriginForNaval && (
                  <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>
                    {origin} بندر نیست — غارت دریایی فقط از قلعه/شهرهای بندری ممکن است
                  </div>
                )}
              </>
            ) : (
              <div className="page-sub" style={{ margin: '10px 4px 0' }}>عملیات دفاعی برای قلعهٔ مبدا — نیازی به مقصد نیست</div>
            )}

            <div className="page-sub" style={{ margin: '10px 4px 0' }}>
              زمان رسیدن لشکر: <b style={{ color: 'var(--az2)' }}>{eta > 0 ? `حدود ${eta.toLocaleString('fa-IR')} دقیقه` : 'بی‌درنگ — همین‌جاست'}</b>
            </div>

            {op.needsTarget && opType !== 'garrison' && (
              <div className="page-sub" style={{ margin: '10px 4px 0' }}>
                سناریوی نبرد اینجا نوشته نمی‌شود — وقتی لشکر برسد، آمار دو طرف رد و بدل می‌شود و تا ۶ ساعت بعد می‌توانی از صفحهٔ «رول‌ها» سناریوی جنگ را بفرستی.
              </div>
            )}
          </div>

          <div className="sect up u3">گسیل نیرو</div>
          <div className="page-sub up u3" style={{ margin: '0 4px 10px' }}>
            هر نیروی عمومی به پادگان و کارگاه تسلیحاتِ همان یگان نیاز دارد؛ کشتی جنگی فقط در قلعه/شهر بندری و بعد از ساخت بندر ممکن است — تا نسازی، ردیفش قفل می‌ماند.
          </div>
          <div className="card up u3">
            {allTroops.map(t => {
              const ok = unlocked(t);
              const req = !t.special && !t.naval && TROOP_UNIT_BUILDINGS[t.id];
              return (
                <div className="troop" key={t.id}>
                  <div className="tn">
                    {t.name}
                    {t.special && <span className="troop-tag">ویژهٔ اقلیم</span>}
                    {t.naval && <span className="troop-tag">ویژهٔ بندر</span>}
                    <small>
                      {t.cost.toLocaleString('fa-IR')} طلا/نفر · {((t.special || t.naval) ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR).toLocaleString('fa-IR')} غله/روز · توان {(t.special ? SPECIAL_POWER : t.power).toLocaleString('fa-IR')}
                    </small>
                    {!ok && req && <small className="troop-locked">نیاز به پادگان و کارگاه تسلیحاتِ این یگان</small>}
                    {!ok && t.naval && <small className="troop-locked">نیاز به ساختن بندر</small>}
                  </div>
                  <input type="number" min="0" value={counts[t.id] || ''} disabled={!ok} placeholder="۰"
                         onChange={e => setCounts({ ...counts, [t.id]: Math.max(0, parseInt(e.target.value, 10) || 0) })} />
                </div>
              );
            })}
            <div className={`cost-grid ${overGold || overMen ? 'over' : ''}`}>
              <div className={`cost-item ${overGold ? 'over' : ''}`}>
                <Coin s={16} />
                <b>{goldCost.toLocaleString('fa-IR')}</b>
                <small>طلا</small>
              </div>
              <div className={`cost-item ${overMen ? 'over' : ''}`}>
                <People s={16} />
                <b>{menCommitted.toLocaleString('fa-IR')}/{men.toLocaleString('fa-IR')}</b>
                <small>نفر</small>
              </div>
              <div className="cost-item">
                <Wheat s={16} />
                <b>{foodPerDay.toLocaleString('fa-IR')}</b>
                <small>غله/روز</small>
              </div>
              <div className="cost-item">
                <Swords s={16} />
                <b>{estPower.toLocaleString('fa-IR')}</b>
                <small>توان</small>
              </div>
            </div>
          </div>

          <div className="up u3">
            <button className="btn" disabled={!!formIssue || busy} onClick={send}>
              {formIssue || (busy ? 'در حال ارسال...' : 'مُهر و ارسال فرمان')}
            </button>
          </div>
        </>
      )}

      {tab === 'reports' && (
        <div className="up u2">
          {mine.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز لشکری نفرستاده‌ای</div>
          )}
          {mine.length > 0 && visibleReports.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              گزارش لشکرکشی تازه، تا نیم ساعت دیگر اینجا ظاهر می‌شود
            </div>
          )}
          {visibleReports.map(c => (
            <div className="card" key={c.id} style={{ marginBottom: 10 }}>
              <div className="res">
                <div className="ic"><Swords s={16} /></div>
                <div className="n">
                  {c.name}
                  <small>{c.op_name} · فرستنده: {c.sender}</small>
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--low)', margin: '8px 0' }}>
                {c.origin} ← {c.target}
                {' · '}
                {!c.active ? 'لغوشده'
                  : c.arrived ? 'رسیده به مقصد'
                  : `در راه — حدود ${c.travel_minutes.toLocaleString('fa-IR')} دقیقه تا رسیدن`}
              </div>
              {c.active && (
                <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} onClick={() => cancelCampaign(c)}>لغو لشکر</button>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
