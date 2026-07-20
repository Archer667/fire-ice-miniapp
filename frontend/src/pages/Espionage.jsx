import { useEffect, useMemo, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic } from '../telegram.js';
import { Eye, Swords, Bastion, Coin, Wheat, People, Wood, Rock, Pick, Wine } from '../components/Icons.jsx';
import WesterosMap from '../components/WesterosMap.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { SPY_GOLD_COST, SPY_MEN_COST, spyTravelMinutes, RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE } from '../gamedata.js';

const RES_ICONS = [
  { key: 'gold', Icon: Coin, name: 'طلا' },
  { key: 'food', Icon: Wheat, name: 'غله' },
  { key: 'men', Icon: People, name: 'نفرات' },
  { key: 'wood', Icon: Wood, name: 'چوب' },
  { key: 'stone', Icon: Rock, name: 'سنگ' },
  { key: 'iron', Icon: Pick, name: 'آهن' },
  { key: 'wine', Icon: Wine, name: 'شراب' },
];

const TABS = [
  { key: 'spy',    label: 'جاسوسی' },
  { key: 'rumors', label: 'شایعه' },
];

export default function Espionage() {
  const { me, setMe, toast } = useGame();
  const gold = me.resources.gold;
  const men = me.resources.men ?? 0;

  const [tab, setTab] = useState('spy');
  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [missions, setMissions] = useState(null);
  const [target, setTarget] = useState(null); // { name, region, owner } | null
  const [scenario, setScenario] = useState('');
  const [busy, setBusy] = useState(false);

  const [rumorTarget, setRumorTarget] = useState([]);
  const [rumorText, setRumorText] = useState('');
  const [rumorBusy, setRumorBusy] = useState(false);

  const loadMap = () => {
    setMapError(false);
    api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); });
  };
  const loadMissions = () => api.spyMine().then(setMissions).catch(e => { toast(e.message); setMissions([]); });

  useEffect(() => { loadMap(); loadMissions(); }, []);

  const rumorTextTooShort = rumorText.trim().length < 10;
  const overRumorGold = gold < RUMOR_GOLD_COST;

  const sendRumor = async () => {
    if (!rumorTarget.length) { toast('یک لرد را هدف بگیر'); return; }
    if (rumorTextTooShort) { toast('شایعه را کمی بیشتر توضیح بده'); return; }
    if (overRumorGold) { toast('طلای کافی برای پخش این شایعه نداری'); return; }
    setRumorBusy(true);
    try {
      await api.sendRumor(rumorTarget[0].tg_id, rumorText.trim());
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: gold - RUMOR_GOLD_COST } });
      toast(`شایعه علیه «${rumorTarget[0].name}» پخش شد`);
      setRumorTarget([]); setRumorText('');
    } catch (e) { toast(e.message); }
    setRumorBusy(false);
  };

  const eta = useMemo(
    () => (target ? spyTravelMinutes(me.region, target.region) : null),
    [target, me.region]
  );
  const overGold = gold < SPY_GOLD_COST;
  const overMen = men < SPY_MEN_COST;

  const scenarioTooShort = scenario.trim().length < 10;

  const send = async () => {
    if (!target) { toast('یک قلعه را از روی نقشه هدف بگیر'); return; }
    if (!target.owner) { toast('این قلعه صاحبی ندارد که جاسوسی‌اش کنی'); return; }
    if (target.mine) { toast('نمی‌توانی جاسوس به قلعهٔ خودت بفرستی'); return; }
    if (scenarioTooShort) { toast('نقشهٔ جاسوسی‌ات را کمی بیشتر توضیح بده'); return; }
    if (overGold) { toast('خزانه کافی نیست'); return; }
    if (overMen) { toast('نفرات کافی نداری'); return; }
    setBusy(true);
    try {
      await api.sendSpy(target.name, scenario.trim());
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: gold - SPY_GOLD_COST, men: men - SPY_MEN_COST } });
      toast('یگان جاسوسی اعزام شد — سناریو برای بررسی شورای جنگ فرستاده شد');
      setTarget(null);
      setScenario('');
      loadMissions();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <>
      <div className="page-title up">جاسوسی</div>
      <div className="page-sub up">
        {tab === 'spy' ? 'یک قلعه را روی نقشه هدف بگیر تا از منابع، ساختمان‌های نظامی و لشکرکشی‌هایش خبردار شوی'
          : 'کارزار عمومی علیه یک لرد — همه می‌بینند، محبوبیتش کمی افت می‌کند'}
      </div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.key); }}>{t.label}</button>
        ))}
      </div>

      {tab === 'spy' && (
        mapError ? (
          <div className="card up u2" style={{ textAlign: 'center', color: 'var(--mid)' }}>
            نقشه بارگذاری نشد — اتصال به سرور را بررسی کن
            <div style={{ marginTop: 12 }}>
              <button className="btn ghost" style={{ padding: 11 }} onClick={loadMap}>تلاش دوباره</button>
            </div>
          </div>
        ) : !mapData || !missions ? (
          <div className="loading">جاسوس‌ها در راه‌اند...</div>
        ) : (
          <>
            <div className="sect up u2">نقشهٔ وستروس</div>
            <div className="up u2">
              <WesterosMap data={mapData} meCastle={me.castle} pickLabel="انتخاب برای جاسوسی"
                           onSelectTarget={(c) => { haptic(); setTarget(c); }} />
            </div>

            <div className="sect up u3">فرمان جاسوسی</div>
            <div className="card up u3">
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

              <label className="f">نقشهٔ جاسوسی</label>
              <textarea value={scenario} onChange={e => setScenario(e.target.value)}
                        placeholder="یگان جاسوسی‌ات را چطور تربیت و اعزام می‌کنی؟ نقشه‌ات برای نفوذ چیست... (شورای جنگ این را می‌خواند و بر اساسش شانس موفقیتت را مشخص می‌کند)" />

              <div className={`cost ${overGold || overMen ? 'over' : ''}`}>
                <span>هزینهٔ اعزام</span>
                <b>{SPY_GOLD_COST.toLocaleString('fa-IR')} طلا · {SPY_MEN_COST.toLocaleString('fa-IR')} نفر</b>
              </div>
            </div>

            <div className="up u3">
              <button className="btn" disabled={!target || overGold || overMen || scenarioTooShort || busy} onClick={send}>
                {overGold ? 'خزانه کافی نیست' : overMen ? 'نفرات کافی نیست' : busy ? 'در حال اعزام...' : 'تربیت و اعزام یگان جاسوسی'}
              </button>
            </div>

            <div className="sect up u4">ماموریت‌های جاسوسی من</div>
            <div className="up u4">
              {missions.length === 0 && (
                <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز جاسوسی نفرستاده‌ای</div>
              )}
              {missions.map(m => (
                <div className="card" key={m.id} style={{ marginBottom: 10 }}>
                  <div className="res">
                    <div className="ic"><Eye s={16} /></div>
                    <div className="n">
                      {m.target}
                      <small>
                        {!m.arrived ? `در راه — حدود ${m.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر`
                          : !m.resolved ? 'رسیده — منتظر بررسی شورای جنگ'
                          : m.success ? 'گزارش رسید' : 'جاسوس دستگیر شد'}
                      </small>
                    </div>
                  </div>

                  {m.scenario && (
                    <div style={{ marginTop: 10, fontSize: 11.5, color: 'var(--low)', lineHeight: 1.8 }}>
                      نقشه‌ات: «{m.scenario}»
                    </div>
                  )}

                  {m.resolved && m.success === false && (
                    <div style={{ marginTop: 10, fontSize: 12.5, color: 'var(--danger)' }}>
                      جاسوس شناسایی و دستگیر شد — نفرات اعزامی برنگشتند و گزارشی به دست نیامد.
                    </div>
                  )}

                  {m.resolved && m.report && (
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
                            <Bastion s={12} /> {b.name} · سطح {b.level.toLocaleString('fa-IR')}
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
        )
      )}

      {tab === 'rumors' && (
        <div className="card up u2">
          <label className="f" style={{ marginTop: 0 }}>هدف</label>
          <PlayerPicker value={rumorTarget} onChange={setRumorTarget} single />
          <label className="f">متن شایعه</label>
          <textarea value={rumorText} onChange={e => setRumorText(e.target.value)}
                    placeholder="چه شایعه‌ای دربارهٔ این لرد پخش می‌کنی..." />
          <div className="page-sub" style={{ margin: '10px 4px 0' }}>
            هزینه: <b style={{ color: 'var(--az2)' }}>{RUMOR_GOLD_COST.toLocaleString('fa-IR')} طلا</b> ·
            {' '}اثر: <b style={{ color: 'var(--danger)' }}>−{RUMOR_POPULARITY_DAMAGE.toLocaleString('fa-IR')} محبوبیت هدف</b>
          </div>
          <button className="btn" style={{ marginTop: 14 }} disabled={rumorBusy} onClick={sendRumor}>
            {rumorBusy ? 'در حال پخش...' : 'پخش شایعه'}
          </button>
          <div className="page-sub" style={{ margin: '10px 4px 0' }}>
            همهٔ شایعات پخش‌شده را می‌توانی در تب «شایعات» بخش کلاغ‌ها ببینی
          </div>
        </div>
      )}
    </>
  );
}
