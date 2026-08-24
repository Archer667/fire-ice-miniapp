import { useEffect, useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Swords, Coin, People, Wheat } from '../components/Icons.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import {
  COMMON_TROOPS, SPECIAL_COST, SPECIAL_POWER, REGIONS_STATIC, OP_TYPES,
  TROOP_UNIT_BUILDINGS, FOOD_COST_REGULAR, FOOD_COST_SPECIAL, travelMinutes, campaignPower,
  NAVAL_TROOPS, NAVAL_TROOP_IDS, NAVAL_CAMP_BUILDING, WEAPON_NAMES, castleLabel,
  SIEGE_EQUIPMENT, SIEGE_WORKSHOP_BUILDING,
} from '../gamedata.js';

const TABS = [
  { key: 'command', label: 'نقشه و فرمان' },
  { key: 'legions', label: 'لشکرها' },
  { key: 'reports', label: 'گزارش‌ها' },
];
const SEEN_KEY = 'fireice_war_reports_seen';
const loadSeenIds = () => { try { return new Set(JSON.parse(localStorage.getItem(SEEN_KEY)) || []); } catch { return new Set(); } };

function utcMillis(value) {
  if (!value) return NaN;
  const text = String(value);
  return new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`).getTime();
}

function ArrivalCountdown({ arrivalAt, arrived }) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    if (arrived || !arrivalAt) return undefined;
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [arrivalAt, arrived]);
  if (arrived || !arrivalAt) return <>رسیده به مقصد</>;
  const seconds = Math.max(0, Math.ceil((utcMillis(arrivalAt) - nowMs) / 1000));
  if (seconds <= 0) return <>رسیده به مقصد</>;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts = [h > 0 ? `${h.toLocaleString('fa-IR')} ساعت` : '', m > 0 ? `${m.toLocaleString('fa-IR')} دقیقه` : '', `${s.toLocaleString('fa-IR')} ثانیه`].filter(Boolean);
  return <>در راه — {parts.join(' و ')} تا رسیدن</>;
}

export default function War() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const men = me.resources.men ?? 0;

  const [tab, setTab] = useState('command');
  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [buildings, setBuildings] = useState(null);
  const [mine, setMine] = useState(null);
  const [legions, setLegions] = useState(null);
  const [seenIds, setSeenIds] = useState(loadSeenIds);
  const [warWindow, setWarWindow] = useState(null);

  const loadMap = () => {
    setMapError(false);
    api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); });
  };
  const loadMine = () => api.warMine().then(setMine).catch(e => { toast(e.message); setMine([]); });
  const loadLegions = () => api.legions().then(setLegions).catch(e => { toast(e.message); setLegions([]); });
  const loadWarWindow = () => api.warWindow().then(setWarWindow).catch(() => setWarWindow({ open: true }));

  useEffect(() => {
    loadMap(); loadMine(); loadLegions(); loadWarWindow();
    const mapTimer = setInterval(loadMap, 30000);
    const armyTimer = setInterval(() => { loadMine(); loadLegions(); }, 15000);
    return () => { clearInterval(mapTimer); clearInterval(armyTimer); };
  }, []);
  const windowClosed = warWindow ? !warWindow.open : false;

  const visibleReports = mine || [];

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

  const stationedOrigins = useMemo(
    () => (mine || []).filter(c => c.active && c.op_type === 'garrison' && c.arrived).map(c => c.target),
    [mine]
  );
  const myCastles = [me.castle, ...(me.castles || [])];
  const originOptions = [...new Set([...myCastles, ...stationedOrigins])];

  const [origin, setOrigin] = useState(me.castle);
  const [opType, setOpType] = useState(OP_TYPES[0].id);
  const [target, setTarget] = useState(null); // { name, region, ... } | null
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelBusyId, setCancelBusyId] = useState(null);
  const [movingLegion, setMovingLegion] = useState(null);
  const [attackBusyId, setAttackBusyId] = useState(null);

  // اطلاعاتِ هر قلعه (اقلیمِ واقعی، بندری‌بودن، نوعِ زمین) از خودِ دادهٔ نقشه —
  // چون قلعهٔ دومِ یه لرد می‌تونه در اقلیمِ دیگه‌ای باشه یا بندری/غیربندری متفاوت
  // از قلعهٔ اصلی‌اش، پس نباید بر اساسِ اقلیمِ خانگیِ بازیکن حدس زده بشه
  const castleInfo = useMemo(() => {
    const m = {};
    for (const r of (mapData?.regions || [])) for (const c of r.castles) m[c.name] = { ...c, region: r.id };
    return m;
  }, [mapData]);
  const isPortCastle = (name) => castleInfo[name] ? !!castleInfo[name].port : (name === me.castle && me.is_port);
  const isSeaOnlyCastle = (name) => castleInfo[name]?.terrain === 'sea';

  // نیروهای ویژه/دریایی قابل‌ساخت، بر اساسِ اقلیم و بندری‌بودنِ خودِ قلعهٔ مبدا
  // (نه اقلیمِ خانگیِ بازیکن) — همینه که با عوض‌شدنِ مبدا فرق می‌کنه
  const originRegion = castleInfo[origin]?.region || me.region;
  const specials = REGIONS_STATIC[originRegion]?.special || [];
  const allTroops = [
    ...COMMON_TROOPS.map(t => ({ ...t, special: false })),
    ...specials.map(n => ({ id: n, name: n, cost: SPECIAL_COST, special: true })),
    ...(isPortCastle(origin) ? NAVAL_TROOPS.map(t => ({ ...t, special: false, naval: true })) : []),
  ];

  const [counts, setCounts] = useState(Object.fromEntries(allTroops.map(t => [t.id, 0])));
  const [equipmentCounts, setEquipmentCounts] = useState(Object.fromEntries(SIEGE_EQUIPMENT.map(e => [e.id, 0])));

  const op = OP_TYPES.find(o => o.id === opType);

  // بازدهی/توان حمله بر اساسِ ساختمان‌های همون قلعه‌ای‌ست که لشکر واقعاً ازش اعزام
  // می‌شه — پس با عوض‌شدنِ مبدا، ساختمان‌های همون قلعه رو دوباره می‌خونیم
  useEffect(() => {
    let cancelled = false;
    api.buildings(origin).then(d => { if (!cancelled) setBuildings(d.buildings); }).catch(() => { if (!cancelled) setBuildings([]); });
    return () => { cancelled = true; };
  }, [origin]);

  // لیستِ نیروهای قابل‌ساخت با عوض‌شدنِ مبدا فرق می‌کنه (نیروی ویژه/کشتی) — شمارشِ
  // قبلی که ممکنه دیگه معتبر نباشه رو پاک می‌کنیم تا فرمانِ بعدی نیرویِ نامعتبر نداشته باشه
  useEffect(() => {
    setCounts(Object.fromEntries(allTroops.map(t => [t.id, 0])));
    setEquipmentCounts(Object.fromEntries(SIEGE_EQUIPMENT.map(e => [e.id, 0])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin]);

  const sameCastle = !op.needsTarget || (target && target.name === origin);
  const targetName = op.needsTarget && target ? target.name : origin;
  const badOriginForNaval = op.portOnly && !isPortCastle(origin);
  const originIsSeaOnly = !sameCastle && isSeaOnlyCastle(origin);

  const [routeOptions, setRouteOptions] = useState(null); // [{minutes, path}] | null
  const [routeChoice, setRouteChoice] = useState(0);
  const [routeError, setRouteError] = useState('');
  useEffect(() => {
    if (sameCastle || !targetName) { setRouteOptions(null); setRouteChoice(0); setRouteError(''); return; }
    let cancelled = false;
    setRouteOptions(null);
    setRouteError('');
    api.warRoutes(origin, targetName).then(res => {
      if (!cancelled) { setRouteOptions(res.routes || []); setRouteChoice(0); }
    }).catch(e => { if (!cancelled) { setRouteOptions([]); setRouteError(e.message || 'مسیری پیدا نشد'); } });
    return () => { cancelled = true; };
  }, [origin, targetName, sameCastle]);

  const chosenRoute = routeOptions && routeOptions[routeChoice];
  const equipmentSlowdown = Math.min(1, SIEGE_EQUIPMENT.reduce((s, e) => s + (equipmentCounts[e.id] || 0) * e.slowdown, 0));
  const baseEta = sameCastle ? 0 : (chosenRoute ? chosenRoute.minutes : travelMinutes(sameCastle, origin, targetName));
  const eta = Math.round(baseEta * (1 + equipmentSlowdown));

  const unlocked = (troop) => {
    if (troop.naval) return builtLevels[NAVAL_CAMP_BUILDING] > 0;
    if (troop.special) return true;
    const req = TROOP_UNIT_BUILDINGS[troop.id];
    if (!req) return true;
    return builtLevels[req.camp] > 0;
  };

  const goldCost = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * t.cost, 0),
    [counts]
  );
  const equipmentCost = useMemo(() => {
    const total = {};
    for (const equipment of SIEGE_EQUIPMENT) {
      const count = equipmentCounts[equipment.id] || 0;
      for (const [resource, amount] of Object.entries(equipment.cost)) total[resource] = (total[resource] || 0) + amount * count;
    }
    return total;
  }, [equipmentCounts]);
  const menCommitted = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0), 0),
    [counts]
  );
  const foodPerDay = useMemo(
    () => allTroops.reduce((s, t) => s + (counts[t.id] || 0) * ((t.special || t.naval) ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR), 0),
    [counts]
  );
  const weaponsNeeded = useMemo(() => {
    const need = {};
    for (const t of allTroops) {
      const n = counts[t.id] || 0;
      if (n <= 0 || t.special || t.naval) continue;
      const weaponKey = TROOP_UNIT_BUILDINGS[t.id]?.weapon;
      if (weaponKey) need[weaponKey] = (need[weaponKey] || 0) + n;
    }
    return need;
  }, [counts]);
  const shortWeapon = Object.entries(weaponsNeeded).find(([wkey, n]) => n > (me.resources[wkey] ?? 0));
  const estPower = useMemo(() => campaignPower(counts, builtLevels), [counts, builtLevels]);
  const totalGoldCost = goldCost + (equipmentCost.gold || 0);
  const overGold = totalGoldCost > gold;
  const shortEquipmentResource = Object.entries(equipmentCost).find(([resource, amount]) => resource !== 'gold' && amount > (me.resources[resource] || 0));
  const overMen = menCommitted > men;
  const badPortTarget = op.portOnly && target && !target.port;
  const seaCapacity = useMemo(
    () => NAVAL_TROOP_IDS.reduce((s, tid) => s + (counts[tid] || 0) * NAVAL_TROOPS.find(t => t.id === tid).capacity, 0),
    [counts]
  );
  const seaLandMen = useMemo(
    () => allTroops.reduce((s, t) => s + (t.naval ? 0 : (counts[t.id] || 0)), 0),
    [counts]
  );
  const overSeaCapacity = originIsSeaOnly && seaLandMen > seaCapacity;
  const overSeaRoute = !!chosenRoute?.via_sea && seaLandMen > seaCapacity;
  const targetPeacePact = ['non_aggression', 'full_alliance'].includes(target?.owner?.pact) ? target.owner.pact : null;
  const hostileAgainstPact = !!targetPeacePact && ['attack', 'siege', 'naval_raid'].includes(opType);
  const formIssue = windowClosed ? 'پنجرهٔ لشکرکشی بسته است'
    : movingLegion && !target ? 'مقصد را انتخاب کن'
    : movingLegion && target?.name === movingLegion.target ? 'مقصد جدید باید متفاوت باشد'
    : movingLegion ? null
    : overGold ? 'خزانه کافی نیست'
    : overMen ? 'نفرات کافی نیست'
    : shortWeapon ? `${WEAPON_NAMES[shortWeapon[0]]} کافی نیست`
    : shortEquipmentResource ? `${shortEquipmentResource[0]} کافی برای ساخت ادوات نداری`
    : (op.needsTarget && !target) ? 'مقصد را انتخاب کن'
    : hostileAgainstPact ? 'با صاحب این قلعه پیمان داری؛ فقط جای‌گیری مجاز است'
    : badPortTarget ? 'مقصد باید بندر باشد'
    : badOriginForNaval ? 'مبدا باید بندر باشد'
    : overSeaCapacity ? `مبدا کاملاً دریایی است — کشتی‌های این فرمان فقط ${seaCapacity.toLocaleString('fa-IR')} نفر را جابه‌جا می‌کنند`
    : overSeaRoute ? `این مسیر از آب می‌گذرد — کشتی‌های این فرمان فقط ${seaCapacity.toLocaleString('fa-IR')} نفر را جابه‌جا می‌کنند، کشتی بیشتری اضافه کن یا مسیرِ دیگری انتخاب کن`
    : menCommitted <= 0 ? 'نیرویی گسیل نکرده‌ای'
    : null;

  const resetForm = () => {
    setName(''); setTarget(null);
    setCounts(Object.fromEntries(allTroops.map(t => [t.id, 0])));
    setEquipmentCounts(Object.fromEntries(SIEGE_EQUIPMENT.map(e => [e.id, 0])));
  };

  const send = async () => {
    if (windowClosed) { toast('پنجرهٔ لشکرکشی الان بسته است'); return; }
    if (op.needsTarget && !target) { toast('مقصد را از روی نقشه یا لیست انتخاب کن'); return; }
    if (op.portOnly && target && !target.port) { toast('غارت دریایی فقط علیه اهداف بندری ممکن است'); return; }
    if (badOriginForNaval) { toast('غارت دریایی فقط از قلعه/شهرهای بندری ممکن است'); return; }
    if (!movingLegion && overSeaCapacity) { toast(`مبدا کاملاً دریایی است — کشتی‌های این فرمان فقط ${seaCapacity.toLocaleString('fa-IR')} نفر را جابه‌جا می‌کنند`); return; }
    if (!movingLegion && overSeaRoute) { toast(`این مسیر از آب می‌گذرد — کشتی‌های این فرمان فقط ${seaCapacity.toLocaleString('fa-IR')} نفر را جابه‌جا می‌کنند`); return; }
    if (movingLegion) {
      if (!target) { toast('مقصد جدید لشکر را از روی نقشه انتخاب کن'); return; }
      setBusy(true);
      try {
        const res = await api.moveCampaign(movingLegion.id, {
          target_castle: target.name, op_type: opType,
          via: chosenRoute ? chosenRoute.path : undefined,
        });
        haptic('medium');
        toast(`فرمان حرکت صادر شد — حدود ${(res.travel_minutes || 0).toLocaleString('fa-IR')} دقیقه تا مقصد`);
        setMovingLegion(null); setTarget(null); loadMine(); loadLegions();
      } catch (e) { toast(e.message); }
      setBusy(false);
      return;
    }
    if (menCommitted <= 0) { toast('هیچ نیرویی گسیل نکرده‌ای'); return; }
    if (overGold) { toast('خزانه کافی نیست'); return; }
    if (overMen) { toast('نفرات کافی نداری'); return; }
    if (shortWeapon) { toast(`${WEAPON_NAMES[shortWeapon[0]]} کافی نداری`); return; }
    setBusy(true);
    try {
      await api.submitCampaign({
        origin_castle: origin, op_type: opType,
        target_castle: op.needsTarget ? target.name : null,
        name: name.trim(), troops: counts,
        equipment: equipmentCounts,
        via: chosenRoute ? chosenRoute.path : undefined,
      });
      haptic('medium');
      const weaponUpdates = Object.fromEntries(
        Object.entries(weaponsNeeded).map(([wkey, n]) => [wkey, (me.resources[wkey] ?? 0) - n])
      );
      setMe({
        ...me,
        resources: Object.fromEntries(Object.entries({ ...me.resources, gold: gold - goldCost, men: men - menCommitted, ...weaponUpdates }).map(([k, v]) => [k, v - (equipmentCost[k] || 0)])),
        active_campaigns: (me.active_campaigns ?? 0) + 1,
      });
      toast(eta > 0 ? `فرمان مُهر شد — لشکر تا ${eta.toLocaleString('fa-IR')} دقیقه دیگر می‌رسد` : 'فرمان مُهر شد — لشکر همین‌جاست');
      resetForm();
      loadMine(); loadMap(); loadLegions();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  const cancelCampaign = async (c) => {
    if (cancelBusyId) return;
    setCancelBusyId(c.id);
    try {
      const res = await api.cancelCampaign(c.id);
      haptic('medium');
      api.me().then(setMe);
      toast(res.penalty_applied
        ? 'لشکر لغو شد؛ چون بیشتر از ۵ دقیقه گذشته بود، فقط ۵۰٪ نفرات و هزینه‌ها برگشت'
        : 'لشکر در مهلت ۵ دقیقه‌ای لغو شد و تمام نفرات و هزینه‌ها برگشت');
      loadMine(); loadMap(); loadLegions();
    } catch (e) { toast(e.message); }
    setCancelBusyId(null);
  };

  const relaunchFrom = (c) => {
    haptic();
    setMovingLegion(c);
    setOrigin(c.target);
    setOpType('garrison');
    setTarget(null);
    setTab('command');
    toast(`لشکر «${c.name}» انتخاب شد — مقصد جدیدش را از روی نقشه مشخص کن`);
  };

  const orderAttack = async (c) => {
    setAttackBusyId(c.id);
    try {
      await api.orderSiegeAttack(c.id);
      haptic('medium'); toast('دستور حمله صادر شد — لشکر و مدافعان تا اعلام نتیجه قفل می‌شوند');
      loadLegions(); loadMine();
    } catch (e) { toast(e.message); }
    setAttackBusyId(null);
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
          {windowClosed && (
            <div className="card up u1" style={{ borderColor: 'var(--danger)', textAlign: 'center', color: 'var(--danger)', fontSize: 12.5 }}>
              پنجرهٔ لشکرکشی الان بسته است — ادمین باید بازش کند تا بتوانی فرمان گسیل بدهی. نقشه و لشکرهای در راه دست‌نخورده‌اند.
            </div>
          )}
          <div className="sect up u2">نقشهٔ وستروس</div>
          <div className="up u2">
            <WesterosMap data={mapData} meCastles={[me.castle, ...(me.castles || [])]} onSelectTarget={(c) => { haptic(); setTarget(c); toast(`${castleLabel(c.name)} به‌عنوان مقصد انتخاب شد`); }}
                         routePath={!sameCastle ? chosenRoute?.path : null} />
          </div>

          <div className="sect up u3">ساخت لشکر</div>
          <div className="card up u3">
            {movingLegion && (
              <div style={{ marginBottom: 12, padding: 10, borderRadius: 12, background: 'rgba(77,163,255,.08)', color: 'var(--az2)', fontSize: 12 }}>
                در حال جابه‌جایی همان لشکر «{movingLegion.name}» با {movingLegion.men_committed.toLocaleString('fa-IR')} نفر؛ هیچ نفر، طلا یا سلاح تازه‌ای کم نمی‌شود.
                <button className="btn ghost" style={{ marginTop: 8, padding: 8 }} onClick={() => { setMovingLegion(null); setTarget(null); }}>لغو فرمان حرکت</button>
              </div>
            )}
            <label className="f" style={{ marginTop: 0 }}>نام لشکر</label>
            <input value={name} onChange={e => setName(e.target.value)} maxLength={60} placeholder="مثلاً «یورش بامداد» — اختیاری" />

            <label className="f">مبدا</label>
            <select value={origin} disabled={!!movingLegion} onChange={e => setOrigin(e.target.value)}>
              {movingLegion && !originOptions.includes(movingLegion.target) && <option value={movingLegion.target}>{castleLabel(movingLegion.target)} (محل فعلی لشکر)</option>}
              {originOptions.map(o => <option key={o} value={o}>{castleLabel(o)}{myCastles.includes(o) ? ' (قلعهٔ خودت)' : ' (لشکر مستقر)'}</option>)}
            </select>

            <label className="f">نوع عملیات</label>
            <select value={opType} onChange={e => { setOpType(e.target.value); setTarget(null); }}>
              {OP_TYPES.filter(o => !movingLegion || o.id !== 'defense').map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>

            {op.needsTarget ? (
              <>
                <label className="f">مقصد</label>
                <div className="target-pick">
                  {target ? (
                    <>
                      <span>{castleLabel(target.name)}</span>
                      <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11.5 }} onClick={() => setTarget(null)}>پاک‌کردن</button>
                    </>
                  ) : <span style={{ color: 'var(--mid)' }}>از روی نقشه در بالا انتخاب کن</span>}
                </div>
                {op.portOnly && target && !target.port && (
                  <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>
                    {castleLabel(target.name)} بندر نیست — غارت دریایی فقط علیه اهداف بندری ممکن است
                  </div>
                )}
                {op.portOnly && badOriginForNaval && (
                  <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>
                    {castleLabel(origin)} بندر نیست — غارت دریایی فقط از قلعه/شهرهای بندری ممکن است
                  </div>
                )}
              </>
            ) : (
              <div className="page-sub" style={{ margin: '10px 4px 0' }}>عملیات دفاعی برای قلعهٔ مبدا — نیازی به مقصد نیست</div>
            )}

            <div className="page-sub" style={{ margin: '10px 4px 0' }}>
              زمان رسیدن لشکر: <b style={{ color: 'var(--az2)' }}>{eta > 0 ? `حدود ${eta.toLocaleString('fa-IR')} دقیقه` : 'بی‌درنگ — همین‌جاست'}</b>
            </div>

            {!sameCastle && targetName && (
              routeOptions === null ? (
                <div className="page-sub" style={{ margin: '8px 4px 0' }}>در حال یافتن مسیر...</div>
              ) : routeOptions.length > 0 ? (
                <div style={{ marginTop: 10 }}>
                  <label className="f" style={{ marginTop: 0 }}>
                    مسیر لشکرکشی{routeOptions.length > 1 ? ' — یکی رو انتخاب کن' : ''}
                  </label>
                  {routeOptions.map((r, i) => (
                    <div key={i}
                         onClick={() => { if (routeOptions.length > 1) { haptic(); setRouteChoice(i); } }}
                         className={`pick ${routeChoice === i ? 'sel' : ''}`}
                         style={{ marginBottom: 6, textAlign: 'right', cursor: routeOptions.length > 1 ? 'pointer' : 'default' }}>
                      <div className="n" style={{ fontSize: 11.5, lineHeight: 1.9 }}>
                        {r.path.map(castleLabel).join('  ←  ')}
                      </div>
                      <div className="c">
                        {r.minutes.toLocaleString('fa-IR')} دقیقه{routeOptions.length > 1 && i === 0 ? ' · کوتاه‌ترین' : ''}
                        {r.via_sea ? ' · ⚓ از آب می‌گذرد، نیازمند کشتی' : ''}
                      </div>
                    </div>
                  ))}
                </div>
              ) : routeError && (
                <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>{routeError}</div>
              )
            )}

            {op.needsTarget && opType !== 'garrison' && (
              <div className="page-sub" style={{ margin: '10px 4px 0' }}>
                سناریوی نبرد اینجا نوشته نمی‌شود — وقتی لشکر برسد، آمار دو طرف رد و بدل می‌شود و تا ۶ ساعت بعد می‌توانی از صفحهٔ «رول‌ها» سناریوی جنگ را بفرستی.
              </div>
            )}
          </div>

          {!movingLegion && <><div className="sect up u3">گسیل نیرو</div>
          <div className="page-sub up u3" style={{ margin: '0 4px 10px' }}>
            هر نیروی عمومی به پادگانِ همان یگان نیاز دارد؛ کارگاه تسلیحاتش هم لازم است اما فقط برای تولید تسلیحات — هر سرباز موقع اعزام یک واحد از تسلیحاتِ همان یگان مصرف می‌کند. کشتی جنگی فقط در قلعه/شهر بندری و بعد از ساخت بندر ممکن است.
          </div>
          <div className="card up u3">
            {allTroops.map(t => {
              const ok = unlocked(t);
              const weaponKey = !t.special && !t.naval && TROOP_UNIT_BUILDINGS[t.id]?.weapon;
              const weaponStock = weaponKey ? (me.resources[weaponKey] ?? 0) : null;
              const weaponShort = weaponKey && (counts[t.id] || 0) > weaponStock;
              return (
                <div className="troop" key={t.id}>
                  <div className="tn">
                    {t.name}
                    {t.special && <span className="troop-tag">ویژهٔ اقلیم</span>}
                    {t.naval && <span className="troop-tag">ویژهٔ بندر</span>}
                    <small>
                      {t.cost.toLocaleString('fa-IR')} طلا/نفر · {((t.special || t.naval) ? FOOD_COST_SPECIAL : FOOD_COST_REGULAR).toLocaleString('fa-IR')} غله/روز · توان {(t.special ? SPECIAL_POWER : t.power).toLocaleString('fa-IR')}
                      {weaponKey && ok && ` · ${weaponStock.toLocaleString('fa-IR')} ${WEAPON_NAMES[weaponKey]} موجود`}
                    </small>
                    {!ok && weaponKey && <small className="troop-locked">نیاز به پادگانِ این یگان</small>}
                    {!ok && t.naval && <small className="troop-locked">نیاز به ساختن بندر</small>}
                    {ok && weaponShort && <small className="troop-locked">{WEAPON_NAMES[weaponKey]} کافی نیست</small>}
                  </div>
                  <input type="number" min="0" value={counts[t.id] || ''} disabled={!ok} placeholder="۰"
                         onChange={e => setCounts({ ...counts, [t.id]: Math.max(0, parseInt(e.target.value, 10) || 0) })} />
                </div>
              );
            })}
            <div className="sect" style={{ margin: '16px 0 7px' }}>ادوات نظامی</div>
            <div className="page-sub" style={{ marginBottom: 8 }}>
              سطح کارگاه مهندسی ادوات این قلعه: {(builtLevels[SIEGE_WORKSHOP_BUILDING] || 0).toLocaleString('fa-IR')} از ۳ · ادوات نفرات مصرف نمی‌کنند اما سرعت لشکر را کم می‌کنند.
            </div>
            {SIEGE_EQUIPMENT.map(equipment => {
              const unlockedEquipment = (builtLevels[SIEGE_WORKSHOP_BUILDING] || 0) >= equipment.level;
              return (
                <div className="troop" key={equipment.id}>
                  <div className="tn">
                    {equipment.name}<span className="troop-tag">سطح {equipment.level.toLocaleString('fa-IR')}</span>
                    <small>توان محاصره {equipment.siege_power.toLocaleString('fa-IR')} · هزینه هر عدد: {Object.entries(equipment.cost).map(([k,v]) => `${v.toLocaleString('fa-IR')} ${k}`).join('، ')}</small>
                    {!unlockedEquipment && <small className="troop-locked">نیاز به کارگاه مهندسی ادوات سطح {equipment.level.toLocaleString('fa-IR')}</small>}
                  </div>
                  <input type="number" min="0" max="100" value={equipmentCounts[equipment.id] || ''} disabled={!unlockedEquipment} placeholder="۰"
                         onChange={ev => setEquipmentCounts({ ...equipmentCounts, [equipment.id]: Math.max(0, Math.min(100, parseInt(ev.target.value, 10) || 0)) })} />
                </div>
              );
            })}
            <div className={`cost-grid ${overGold || overMen ? 'over' : ''}`}>
              <div className={`cost-item ${overGold ? 'over' : ''}`}>
                <Coin s={16} />
                <b>{totalGoldCost.toLocaleString('fa-IR')}</b>
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
          </div></>}

          <div className="up u3">
            <button className="btn" disabled={!!formIssue || busy} onClick={send}>
              {formIssue || (busy ? 'در حال ارسال...' : movingLegion ? 'صدور فرمان حرکت همین لشکر' : 'مُهر و ارسال فرمان')}
            </button>
          </div>
        </>
      )}

      {tab === 'legions' && (
        <div className="up u2">
          <div className="page-sub" style={{ margin: '0 4px 10px' }}>
            همهٔ لشکرهای فعالت — از جمله دفاعی و جای‌گیری‌ها؛ لغو کردن، طلا و نفرات و تسلیحات مصرف‌شده (منهای غلهٔ خرج‌شده) را برمی‌گرداند
          </div>
          {legions === null && <div className="loading">در حال بارگذاری...</div>}
          {legions && legions.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هیچ لشکر فعالی نداری</div>
          )}
          {legions && legions.map(c => (
            <div className="card" key={c.id} style={{ marginBottom: 10 }}>
              <div className="res">
                <div className="ic"><Swords s={16} /></div>
                <div className="n">
                  {c.name}
                  <small>{c.op_name} · توان {c.power.toLocaleString('fa-IR')} · {c.men_committed.toLocaleString('fa-IR')} نفر</small>
                </div>
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--mid)', margin: '8px 0' }}>
                نیروها: {c.troops.length ? c.troops.map(t => `${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ') : '—'}
              </div>
              {c.route_path && c.route_path.length > 2 ? (
                <div style={{ fontSize: 11, color: 'var(--low)', marginBottom: 4 }}>
                  مسیر: {c.route_path.map(castleLabel).join('  ←  ')}
                </div>
              ) : (
                <div style={{ fontSize: 11, color: 'var(--low)', marginBottom: 4 }}>
                  {castleLabel(c.origin)} ← {castleLabel(c.target)}
                </div>
              )}
              <div style={{ fontSize: 11, color: 'var(--low)', marginBottom: 10 }}>
                <ArrivalCountdown arrivalAt={c.arrival_at} arrived={c.arrived} />
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {c.engagement_locked && (
                  <div style={{ flex: 1, fontSize: 11, color: 'var(--danger)', alignSelf: 'center' }}>
                    {c.waiting_for_result ? 'حمله رسیده — منتظر نتیجهٔ ادمین' : 'درگیر نبرد — تا ثبت نتیجه قفل است'}
                  </div>
                )}
                {hostileAgainstPact && (
                  <div className="page-sub" style={{ margin: '8px 4px 0', color: 'var(--danger)' }}>
                    با صاحب این قلعه {targetPeacePact === 'full_alliance' ? 'اتحاد کامل' : 'پیمان عدم تجاوز'} داری؛ حمله، محاصره و غارت ممنوع است. نوع عملیات را روی «جای‌گیری» بگذار.
                  </div>
                )}
                {c.can_move && (
                  <button className="btn ghost" style={{ padding: 10, fontSize: 12, flex: 1 }} onClick={() => relaunchFrom(c)}>حرکت بده</button>
                )}
                {c.can_attack && (
                  <button className="btn" style={{ padding: 10, fontSize: 12, flex: 1 }} disabled={attackBusyId === c.id} onClick={() => orderAttack(c)}>{attackBusyId === c.id ? '...' : 'دستور حمله'}</button>
                )}
                <button className="btn ghost" style={{ padding: 10, fontSize: 12, flex: 1 }} disabled={cancelBusyId === c.id || c.engagement_locked} onClick={() => cancelCampaign(c)}>
                  {cancelBusyId === c.id ? '...' : 'لغو لشکر'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'reports' && (
        <div className="up u2">
          <div className="page-sub" style={{ margin: '0 4px 10px' }}>گزارش لشکرکشی‌های همهٔ بازیکنان؛ گزارش‌های قدیمی ۲۴ ساعت بعد از رسیدن از این فهرست خارج می‌شوند.</div>
          {visibleReports.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز گزارشی از لشکرکشی‌ها نیست</div>
          )}
          {visibleReports.map(c => (
            <div className="card" key={c.id} style={{ marginBottom: 10 }}>
              <div className="res">
                <div className="ic"><Swords s={16} /></div>
                <div className="n">
                  {c.name}
                  <small>{c.mine ? c.op_name : 'لشکرکشی'} · فرستنده: {c.sender}</small>
                </div>
              </div>
              {c.route_path && c.route_path.length > 2 ? (
                <div style={{ fontSize: 11, color: 'var(--low)', margin: '8px 0 4px' }}>
                  مسیر: {c.route_path.map(castleLabel).join('  ←  ')}
                </div>
              ) : (
                <div style={{ fontSize: 11, color: 'var(--low)', margin: '8px 0 4px' }}>
                  {castleLabel(c.origin)} ← {castleLabel(c.target)}
                </div>
              )}
              <div style={{ fontSize: 11, color: 'var(--low)', marginBottom: 8 }}>
                {!c.active ? 'لغوشده'
                  : <ArrivalCountdown arrivalAt={c.arrival_at} arrived={c.arrived} />}
              </div>
              {c.active && (
                <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} disabled={cancelBusyId === c.id} onClick={() => cancelCampaign(c)}>
                  {cancelBusyId === c.id ? '...' : 'لغو لشکر'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

