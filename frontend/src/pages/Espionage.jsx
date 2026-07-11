import { useEffect, useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Eye, Swords, Shield, Coin, Wheat, People, Wood, Rock, Pick, Wine } from '../components/Icons.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import { SPY_GOLD_COST, SPY_MEN_COST, spyTravelMinutes } from '../gamedata.js';

const RES_ICONS = [
  { key: 'gold', Icon: Coin, name: 'طلا' },
  { key: 'food', Icon: Wheat, name: 'غله' },
  { key: 'men', Icon: People, name: 'نفرات' },
  { key: 'wood', Icon: Wood, name: 'چوب' },
  { key: 'stone', Icon: Rock, name: 'سنگ' },
  { key: 'iron', Icon: Pick, name: 'آهن' },
  { key: 'wine', Icon: Wine, name: 'شراب' },
];

export default function Espionage() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const men = me.resources.men ?? 0;

  const [mapData, setMapData] = useState(null);
  const [missions, setMissions] = useState(null);
  const [target, setTarget] = useState(null); // { name, region, owner } | null
  const [busy, setBusy] = useState(false);

  const loadMap = () => api.map().then(setMapData).catch(e => toast(e.message));
  const loadMissions = () => api.spyMine().then(setMissions).catch(e => toast(e.message));

  useEffect(() => { loadMap(); loadMissions(); }, []);

  const eta = useMemo(
    () => (target ? spyTravelMinutes(me.region, target.region) : null),
    [target, me.region]
  );
  const overGold = gold < SPY_GOLD_COST;
  const overMen = men < SPY_MEN_COST;

  const send = async () => {
    if (!target) { toast('یک قلعه را از روی نقشه هدف بگیر'); return; }
    if (!target.owner) { toast('این قلعه صاحبی ندارد که جاسوسی‌اش کنی'); return; }
    if (target.mine) { toast('نمی‌توانی جاسوس به قلعهٔ خودت بفرستی'); return; }
    if (overGold) { toast('خزانه کافی نیست'); return; }
    if (overMen) { toast('نفرات کافی نداری'); return; }
    setBusy(true);
    try {
      await api.sendSpy(target.name);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: gold - SPY_GOLD_COST, men: men - SPY_MEN_COST } });
      toast(`جاسوس گسیل شد — تا ${eta.toLocaleString('fa-IR')} دقیقه دیگر خبر می‌رسد`);
      setTarget(null);
      loadMissions();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  if (!mapData || !missions) return <div className="loading">جاسوس‌ها در راه‌اند...</div>;

  return (
    <>
      <div className="page-title up">جاسوسی</div>
      <div className="page-sub up">یک قلعه را روی نقشه هدف بگیر تا از منابع، ساختمان‌های نظامی و لشکرکشی‌هایش خبردار شوی</div>

      <div className="sect up u1">نقشهٔ وستروس</div>
      <div className="up u1">
        <WesterosMap data={mapData} meCastle={me.castle} pickLabel="انتخاب برای جاسوسی"
                     onSelectTarget={(c) => { haptic(); setTarget(c); }} />
      </div>

      <div className="sect up u2">فرمان جاسوسی</div>
      <div className="card up u2">
        <label className="f" style={{ marginTop: 0 }}>هدف</label>
        <div className="target-pick">
          {target ? (
            <>
              <span>{target.name}{target.mine ? ' (قلعهٔ خودت)' : ''}</span>
              <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11.5 }} onClick={() => setTarget(null)}>پاک‌کردن</button>
            </>
          ) : <span style={{ color: 'var(--mid)' }}>از روی نقشه در بالا انتخاب کن</span>}
        </div>
        {target && (
          <div className="page-sub" style={{ margin: '10px 4px 0' }}>
            زمان رسیدن جاسوس: <b style={{ color: 'var(--az2)' }}>حدود {eta.toLocaleString('fa-IR')} دقیقه</b>
          </div>
        )}
        <div className={`cost ${overGold || overMen ? 'over' : ''}`}>
          <span>هزینهٔ اعزام</span>
          <b>{SPY_GOLD_COST.toLocaleString('fa-IR')} طلا · {SPY_MEN_COST.toLocaleString('fa-IR')} نفر</b>
        </div>
      </div>

      <div className="up u2">
        <button className="btn" disabled={!target || overGold || overMen || busy} onClick={send}>
          {overGold ? 'خزانه کافی نیست' : overMen ? 'نفرات کافی نیست' : busy ? 'در حال اعزام...' : 'اعزام جاسوس'}
        </button>
      </div>

      <div className="sect up u3">ماموریت‌های جاسوسی من</div>
      <div className="up u3">
        {missions.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز جاسوسی نفرستاده‌ای</div>
        )}
        {missions.map(m => (
          <div className="card" key={m.id} style={{ marginBottom: 10 }}>
            <div className="res">
              <div className="ic"><Eye s={16} /></div>
              <div className="n">
                {m.target}
                <small>{!m.arrived ? `در راه — حدود ${m.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر` : (m.success ? 'گزارش رسید' : 'جاسوس دستگیر شد')}</small>
              </div>
            </div>

            {m.arrived && m.success === false && (
              <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--danger)' }}>
                جاسوس شناسایی و دستگیر شد — نفرات اعزامی برنگشتند و گزارشی به دست نیامد.
              </div>
            )}

            {m.arrived && m.report && (
              <div style={{ marginTop: 10 }}>
                <div className="sect" style={{ margin: '0 0 8px' }}>منابع</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                  {RES_ICONS.map(({ key, Icon, name }) => (
                    <span key={key} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: 'var(--mid)' }}>
                      <Icon s={12} /> {(m.report.resources[key] ?? 0).toLocaleString('fa-IR')} {name}
                    </span>
                  ))}
                </div>

                <div className="sect" style={{ margin: '14px 0 8px' }}>ساختمان‌های نظامی</div>
                {m.report.military.length === 0
                  ? <div style={{ fontSize: 11.5, color: 'var(--low)' }}>هیچ پادگان یا کارگاه تسلیحاتی نساخته</div>
                  : m.report.military.map((b, i) => (
                    <div key={i} style={{ fontSize: 11.5, color: 'var(--mid)' }}>{b.name} · سطح {b.level.toLocaleString('fa-IR')}</div>
                  ))}

                <div className="sect" style={{ margin: '14px 0 8px' }}>دفاع</div>
                {m.report.defense.length === 0
                  ? <div style={{ fontSize: 11.5, color: 'var(--low)' }}>هیچ سازهٔ دفاعی‌ای ندارد</div>
                  : m.report.defense.map((b, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--mid)' }}>
                      <Shield s={12} /> {b.name} · سطح {b.level.toLocaleString('fa-IR')}
                    </div>
                  ))}

                <div className="sect" style={{ margin: '14px 0 8px' }}>لشکرکشی‌های در جریان</div>
                {m.report.campaigns.length === 0
                  ? <div style={{ fontSize: 11.5, color: 'var(--low)' }}>لشکری در حرکت نیست</div>
                  : m.report.campaigns.map((c, i) => (
                    <div key={i} className="warband" style={{ marginBottom: 8 }}>
                      <div className="wi"><Swords s={15} /></div>
                      <div className="t">
                        {c.op_name} <b>{c.origin}</b> ← <b>{c.target}</b>
                        <div className="tm">{c.men_committed.toLocaleString('fa-IR')} نفر · {c.arrived ? 'رسیده به مقصد' : 'در راه'}</div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
