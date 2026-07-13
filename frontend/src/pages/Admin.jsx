import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Shield, Plus, Close } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { MapFrame } from '../components/WesterosMap.jsx';
import ZoomPanMap from '../components/ZoomPanMap.jsx';
import { REGION_COORDS } from '../mapCoords.js';
import { WARDEN_GROUPS, REGIONS_STATIC } from '../gamedata.js';

const NEW_CASTLE = '__new__';

const MAP_KINDS = [
  { key: 'castle', label: 'قلعه' },
  { key: 'city',   label: 'شهر' },
  { key: 'ruin',   label: 'مخروبه' },
  { key: 'port',   label: 'بندر ⚓' },
];

const TABS = [
  { key: 'war',    label: 'جنگ' },
  { key: 'map',    label: 'نقشه' },
  { key: 'titles', label: 'مقام‌ها' },
  { key: 'polls',  label: 'رای‌گیری', fullOnly: true },
  { key: 'admins', label: 'ادمین‌ها', fullOnly: true },
];

export default function Admin() {
  const { me, toast } = useGame();
  const isFull = me.admin_role === 'full';
  const availTabs = TABS.filter(t => !t.fullOnly || isFull);
  const [tab, setTab] = useState('war');

  const [campaignsInfo, setCampaignsInfo] = useState(null);
  const [battles, setBattles] = useState(null);
  const [battleParticipants, setBattleParticipants] = useState([]);
  const [battleText, setBattleText] = useState('');
  const [battleBusy, setBattleBusy] = useState(false);
  const [overlordTarget, setOverlordTarget] = useState([]);
  const [overlordRegion, setOverlordRegion] = useState('north');
  const [wardenTarget, setWardenTarget] = useState([]);
  const [wardenGroup, setWardenGroup] = useState('south');
  const [kingTarget, setKingTarget] = useState([]);
  const [epithetTarget, setEpithetTarget] = useState([]);
  const [epithetText, setEpithetText] = useState('');
  const [pollQuestion, setPollQuestion] = useState('');
  const [pollOptions, setPollOptions] = useState(['', '']);
  const [pollEligible, setPollEligible] = useState([]);
  const [polls, setPolls] = useState(null);
  const [admins, setAdmins] = useState(null);
  const [newAdminTarget, setNewAdminTarget] = useState([]);

  const [mapRegion, setMapRegion] = useState('north');
  const [mapData, setMapData] = useState(null);
  const [mapError, setMapError] = useState(false);
  const [mapOptions, setMapOptions] = useState(null);
  const [pendingPin, setPendingPin] = useState(null); // {x,y}
  const [pickName, setPickName] = useState('');
  const [castleQuery, setCastleQuery] = useState('');
  const [castleResultsOpen, setCastleResultsOpen] = useState(false);
  const [newCastleName, setNewCastleName] = useState('');
  const [pinKind, setPinKind] = useState('castle');

  const loadCampaigns = () => api.adminCampaigns().then(setCampaignsInfo).catch(e => toast(e.message));
  const loadBattles = () => api.adminBattles().then(setBattles).catch(e => toast(e.message));
  const loadPolls = () => api.polls().then(setPolls).catch(e => toast(e.message));
  const loadAdmins = () => api.adminListAdmins().then(setAdmins).catch(e => toast(e.message));
  const loadMapData = () => { setMapError(false); api.map().then(setMapData).catch(e => { toast(e.message); setMapError(true); }); };
  const loadMapOptions = () => api.adminMapOptions(mapRegion).then(setMapOptions).catch(e => toast(e.message));

  useEffect(() => {
    loadCampaigns();
    loadBattles();
    loadPolls();
    loadMapData();
    if (isFull) loadAdmins();
  }, []);

  useEffect(() => {
    loadMapOptions();
    resetCastlePicker();
  }, [mapRegion]);

  const filteredCastleOptions = (mapOptions || []).filter(o =>
    !castleQuery.trim() || o.name.includes(castleQuery.trim())
  );

  const pickCastle = (name) => {
    haptic();
    setPickName(name); setCastleQuery(name); setCastleResultsOpen(false);
    setPinKind((mapOptions || []).find(o => o.name === name)?.kind || 'castle');
  };
  const pickNewCastle = () => {
    haptic();
    setPickName(NEW_CASTLE); setNewCastleName(castleQuery.trim()); setCastleResultsOpen(false);
    setPinKind('castle');
  };

  const resetCastlePicker = () => {
    setPendingPin(null); setPickName(''); setCastleQuery(''); setCastleResultsOpen(false);
    setNewCastleName(''); setPinKind('castle');
  };

  const addMapCastle = async () => {
    if (!pendingPin) return;
    if (!pickName) { toast('یک قلعه/شهر را انتخاب کن'); return; }
    const body = { region: mapRegion, x: pendingPin.x, y: pendingPin.y, kind: pinKind };
    if (pickName === NEW_CASTLE) {
      if (!newCastleName.trim()) { toast('نام قلعه/شهر تازه را بنویس'); return; }
      body.new_name = newCastleName.trim();
    } else {
      body.name = pickName;
    }
    try {
      await api.adminAddMapCastle(body);
      haptic('medium');
      toast('قلعه/شهر به نقشه اضافه شد');
      resetCastlePicker();
      loadMapData(); loadMapOptions();
    } catch (e) { toast(e.message); }
  };

  const deleteMapCastle = async (name) => {
    try {
      await api.adminDeleteMapCastle(name);
      haptic('medium');
      toast(`نشانهٔ «${name}» از نقشه حذف شد`);
      loadMapData(); loadMapOptions();
    } catch (e) { toast(e.message); }
  };

  const addToBattleReport = (s) => {
    haptic();
    const toAdd = [{ tg_id: s.tg_id, name: s.player }];
    if (s.target_tg_id) toAdd.push({ tg_id: s.target_tg_id, name: s.target_player });
    setBattleParticipants(prev => {
      const existing = new Set(prev.map(p => p.tg_id));
      return [...prev, ...toAdd.filter(p => !existing.has(p.tg_id))];
    });
    toast('به شرکت‌کننده‌های روایت جنگ اضافه شد');
  };

  const sendBattleReport = async () => {
    if (!battleParticipants.length) { toast('حداقل یک شرکت‌کننده انتخاب کن'); return; }
    if (battleText.trim().length < 10) { toast('روایت جنگ خیلی کوتاه است'); return; }
    setBattleBusy(true);
    try {
      await api.adminCreateBattleReport(battleParticipants.map(p => p.tg_id), battleText.trim());
      haptic('medium');
      toast('روایت جنگ برای شرکت‌کننده‌ها فرستاده شد');
      setBattleParticipants([]); setBattleText('');
      loadBattles();
    } catch (e) { toast(e.message); }
    setBattleBusy(false);
  };

  const setOverlord = async () => {
    if (!overlordTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminSetOverlord(overlordRegion, overlordTarget[0].tg_id);
      haptic('medium');
      toast('بالادستی تعیین شد');
      setOverlordTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setWarden = async () => {
    if (!wardenTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminSetWarden(wardenGroup, wardenTarget[0].tg_id);
      haptic('medium');
      toast('والی تعیین شد');
      setWardenTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setKing = async () => {
    if (!kingTarget.length) { toast('یک والی را انتخاب کن'); return; }
    try {
      await api.adminSetKing(kingTarget[0].tg_id);
      haptic('medium');
      toast('پادشاه/ملکه تعیین شد');
      setKingTarget([]);
    } catch (e) { toast(e.message); }
  };

  const setEpithet = async () => {
    if (!epithetTarget.length || !epithetText.trim()) { toast('لرد و عنوان را مشخص کن'); return; }
    try {
      await api.adminSetEpithet(epithetTarget[0].tg_id, epithetText.trim());
      haptic('medium');
      toast('عنوان ثبت شد');
      setEpithetTarget([]); setEpithetText('');
    } catch (e) { toast(e.message); }
  };

  const createPoll = async () => {
    const opts = pollOptions.map(o => o.trim()).filter(Boolean);
    if (!pollQuestion.trim() || opts.length < 2 || !pollEligible.length) {
      toast('سوال، حداقل دو گزینه، و حداقل یک واجد شرایط لازم است'); return;
    }
    try {
      await api.adminCreatePoll(pollQuestion.trim(), opts, pollEligible.map(p => p.tg_id));
      haptic('medium');
      toast('رای‌گیری ساخته شد');
      setPollQuestion(''); setPollOptions(['', '']); setPollEligible([]);
      loadPolls();
    } catch (e) { toast(e.message); }
  };

  const closePoll = async (id) => {
    try { await api.adminClosePoll(id); haptic(); toast('رای‌گیری بسته شد'); loadPolls(); }
    catch (e) { toast(e.message); }
  };

  const addAdmin = async () => {
    if (!newAdminTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    try {
      await api.adminAddAdmin(newAdminTarget[0].tg_id);
      haptic('medium');
      toast('ادمین محدود اضافه شد');
      setNewAdminTarget([]);
      loadAdmins();
    } catch (e) { toast(e.message); }
  };

  const removeAdmin = async (tgId) => {
    try { await api.adminRemoveAdmin(tgId); haptic(); toast('ادمین حذف شد'); loadAdmins(); }
    catch (e) { toast(e.message); }
  };

  if (!me.admin_role) {
    return (
      <>
        <div className="page-title up">پنل ادمین</div>
        <div className="card up u1" style={{ textAlign: 'center', color: 'var(--mid)' }}>دسترسی نداری</div>
      </>
    );
  }

  return (
    <>
      <div className="page-title up">پنل ادمین</div>
      <div className="page-sub up">{isFull ? 'ادمین کامل' : 'ادمین محدود — فقط لشکرکشی‌ها، روایت جنگ و مقام‌ها'}</div>

      <div className="tabs up u1">
        {availTabs.map(t => (
          <div key={t.key} className={`tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.key); }}>{t.label}</div>
        ))}
      </div>

      {tab === 'war' && (
        <>
          <div className="sect up u2">اطلاعات لشکرکشی‌ها</div>
          <div className="up u2">
            {(!campaignsInfo || campaignsInfo.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز لشکرکشی‌ای ثبت نشده</div>
            )}
            {campaignsInfo && campaignsInfo.map(s => (
              <div className="card" key={s.id} style={{ marginBottom: 10 }}>
                <div className="res">
                  <div className="ic"><Shield s={16} /></div>
                  <div className="n">
                    {s.player}
                    <small>
                      {s.op_name} · {s.from} ← {s.to} · {s.gold_cost.toLocaleString('fa-IR')} طلا ·{' '}
                      {s.men_committed.toLocaleString('fa-IR')} نفر · {s.food_per_day.toLocaleString('fa-IR')} غله/روز ·{' '}
                      {s.travel_minutes.toLocaleString('fa-IR')} دقیقه سفر
                    </small>
                  </div>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', margin: '8px 0' }}>
                  نیروها: {s.troops.length ? s.troops.map(t => `${t.name} × ${t.count.toLocaleString('fa-IR')}`).join(' · ') : '—'}
                </div>
                {s.plan && <div style={{ fontSize: 12, color: 'var(--mid)', margin: '8px 0', lineHeight: 1.8 }}>{s.plan}</div>}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--low)' }}>
                    {s.active ? (s.arrived ? 'رسیده به مقصد' : 'در راه') : 'لغوشده'}
                  </div>
                  <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11 }} onClick={() => addToBattleReport(s)}>
                    افزودن به روایت جنگ
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="sect up u3">روایت جنگ</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>شرکت‌کننده‌ها</label>
            <PlayerPicker value={battleParticipants} onChange={setBattleParticipants} />
            <label className="f">چه اتفاقی افتاد</label>
            <textarea value={battleText} onChange={e => setBattleText(e.target.value)}
                      placeholder="روایت کن بین چه کسانی بود و نتیجه‌اش چه شد..." />
            <button className="btn" style={{ marginTop: 14 }} disabled={battleBusy} onClick={sendBattleReport}>
              {battleBusy ? 'در حال ارسال...' : 'ارسال روایت به شرکت‌کننده‌ها'}
            </button>
          </div>
          <div className="up u3">
            {(!battles || battles.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز روایتی فرستاده نشده</div>
            )}
            {battles && battles.map(b => (
              <div className="card" key={b.id} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginBottom: 6 }}>{b.participants.join(' · ')}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.8 }}>{b.text}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'map' && (
        <>
          <div className="sect up u2">افزودن قلعه/شهر به نقشه</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>اقلیم</label>
            <select value={mapRegion} onChange={e => setMapRegion(e.target.value)}>
              {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
            </select>
            <div className="page-sub" style={{ margin: '10px 4px' }}>روی نقطهٔ خالی از نقشه کلیک کن تا قلعه/شهر تازه‌ای همان‌جا اضافه شود</div>
            {mapError && (
              <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5, margin: '10px 0' }}>
                نقشه بارگذاری نشد — <span style={{ color: 'var(--az2)', cursor: 'pointer' }} onClick={loadMapData}>تلاش دوباره</span>
              </div>
            )}
            {mapData && (() => {
              const r = mapData.regions.find(x => x.id === mapRegion);
              if (!r) return null;
              const coords = { ...(REGION_COORDS[r.id] || {}), ...(r.coords || {}) };
              return (
                <div className="mapview" style={{ marginTop: 4 }}>
                  <ZoomPanMap>
                    <MapFrame region={r} coords={coords} pin={null}
                              onFrameClick={(x, y) => { haptic(); setPendingPin({ x, y }); }} />
                  </ZoomPanMap>
                </div>
              );
            })()}
            {pendingPin && (
              <div style={{ marginTop: 12 }}>
                <label className="f" style={{ marginTop: 0 }}>این نقطه کدام قلعه/شهر است؟</label>
                <div className="ppicker">
                  <input
                    value={castleQuery}
                    onChange={e => { setCastleQuery(e.target.value); setPickName(''); setCastleResultsOpen(true); }}
                    onFocus={() => setCastleResultsOpen(true)}
                    placeholder={mapOptions === null ? 'در حال بارگذاری قلعه/شهرهای این اقلیم...' : 'اسم قلعه یا شهر را جست‌وجو کن...'}
                  />
                  {castleResultsOpen && (
                    <div className="ppicker-results">
                      {mapOptions === null ? (
                        <div className="ppicker-empty">در حال بارگذاری...</div>
                      ) : (
                        <>
                          {filteredCastleOptions.length === 0 && (
                            <div className="ppicker-empty">
                              {mapOptions.length === 0 ? 'همهٔ قلعه/شهرهای این اقلیم روی نقشه جا گرفته‌اند' : 'موردی پیدا نشد'}
                            </div>
                          )}
                          {filteredCastleOptions.map(o => (
                            <div className="ppicker-row" key={o.name} onClick={() => pickCastle(o.name)}>
                              <span>{o.name}{o.kind === 'port' ? ' ⚓ بندر' : ''}</span>
                            </div>
                          ))}
                          <div className="ppicker-row" onClick={pickNewCastle} style={{ color: 'var(--az2)' }}>
                            + قلعه/شهر کاملاً جدید{castleQuery.trim() ? `: «${castleQuery.trim()}»` : '...'}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
                {pickName && pickName !== NEW_CASTLE && (
                  <div className="page-sub" style={{ margin: '8px 4px 0' }}>انتخاب شد: <b style={{ color: 'var(--az2)' }}>{pickName}</b></div>
                )}
                {pickName === NEW_CASTLE && (
                  <>
                    <label className="f">نام تازه</label>
                    <input value={newCastleName} onChange={e => setNewCastleName(e.target.value)} placeholder="مثلاً: هارتزهیل" />
                  </>
                )}
                {pickName && (
                  <>
                    <label className="f">نوع آیکن روی نقشه</label>
                    <div className="grid2">
                      {MAP_KINDS.map(k => (
                        <div key={k.key} className={`pick ${pinKind === k.key ? 'sel' : ''}`}
                             onClick={() => { haptic(); setPinKind(k.key); }}>
                          <div className="n">{k.label}</div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                  <button className="btn" style={{ padding: 11 }} onClick={addMapCastle}>افزودن به نقشه</button>
                  <button className="btn ghost" style={{ padding: 11 }} onClick={resetCastlePicker}>انصراف</button>
                </div>
              </div>
            )}
          </div>

          {mapData && (() => {
            const r = mapData.regions.find(x => x.id === mapRegion);
            if (!r) return null;
            const placedNames = new Set(Object.keys(r.coords || {}));
            const placed = r.castles.filter(c => placedNames.has(c.name));
            if (!placed.length) return null;
            return (
              <>
                <div className="sect up u3">نشانه‌های ثبت‌شدهٔ این اقلیم</div>
                <div className="region-castles up u3">
                  {placed.map(c => (
                    <div className="rc" key={c.name}>
                      <span>{c.name}<small style={{ color: 'var(--low)' }}> · {MAP_KINDS.find(k => k.key === c.kind)?.label || c.kind}</small></span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {c.owner ? <span className="own">{c.owner.name}</span> : <span className="empty">بدون لرد</span>}
                        <button className="btn ghost" style={{ width: 'auto', padding: '6px 10px', fontSize: 11 }}
                                onClick={() => deleteMapCastle(c.name)}>حذف</button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            );
          })()}
        </>
      )}

      {tab === 'titles' && (
        <>
          <div className="sect up u2">تعیین بالادستی</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>اقلیم</label>
            <select value={overlordRegion} onChange={e => setOverlordRegion(e.target.value)}>
              {Object.entries(REGIONS_STATIC).map(([rid, r]) => <option key={rid} value={rid}>{r.name}</option>)}
            </select>
            <label className="f">لرد (باید اهل همین اقلیم باشد — معمولاً برندهٔ رای‌گیری)</label>
            <PlayerPicker value={overlordTarget} onChange={setOverlordTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setOverlord}>ثبت بالادستی</button>
          </div>

          <div className="sect up u2">تعیین والی</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>والی‌نشین</label>
            <select value={wardenGroup} onChange={e => setWardenGroup(e.target.value)}>
              {Object.entries(WARDEN_GROUPS).map(([gid, g]) => <option key={gid} value={gid}>{g.name}</option>)}
            </select>
            <label className="f">لرد (باید الان بالادستی یکی از اقلیم‌های این والی‌نشین باشد)</label>
            <PlayerPicker value={wardenTarget} onChange={setWardenTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setWarden}>ثبت والی</button>
          </div>

          <div className="sect up u3">تعیین پادشاه/ملکه</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>لرد (باید الان یکی از سه والی باشد)</label>
            <PlayerPicker value={kingTarget} onChange={setKingTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={setKing}>ثبت پادشاه/ملکه</button>
          </div>

          <div className="sect up u3">تعیین عنوان (لقب)</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>لرد</label>
            <PlayerPicker value={epithetTarget} onChange={setEpithetTarget} single />
            <label className="f">عنوان تازه</label>
            <input value={epithetText} onChange={e => setEpithetText(e.target.value)} placeholder="مثلاً: شکنندهٔ زنجیرها" />
            <button className="btn" style={{ marginTop: 14 }} onClick={setEpithet}>ثبت عنوان</button>
          </div>
        </>
      )}

      {tab === 'polls' && isFull && (
        <>
          <div className="sect up u2">رای‌گیری تازه</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>سوال</label>
            <textarea value={pollQuestion} onChange={e => setPollQuestion(e.target.value)} placeholder="مثلاً: والی جنوب چه کسی باشد؟" />
            <label className="f">گزینه‌ها</label>
            {pollOptions.map((opt, i) => (
              <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <input value={opt} onChange={e => setPollOptions(pollOptions.map((o, j) => j === i ? e.target.value : o))}
                       placeholder={`گزینهٔ ${(i + 1).toLocaleString('fa-IR')}`} />
                {pollOptions.length > 2 && (
                  <button className="btn ghost" style={{ width: 44, padding: 0, flexShrink: 0 }}
                          onClick={() => setPollOptions(pollOptions.filter((_, j) => j !== i))}><Close s={14} /></button>
                )}
              </div>
            ))}
            <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} onClick={() => setPollOptions([...pollOptions, ''])}>
              <Plus s={14} /> افزودن گزینه
            </button>
            <label className="f">چه کسانی حق رای دارند</label>
            <PlayerPicker value={pollEligible} onChange={setPollEligible} />
            <button className="btn" style={{ marginTop: 14 }} onClick={createPoll}>ساخت رای‌گیری</button>
          </div>

          <div className="sect up u3">رای‌گیری‌های موجود</div>
          <div className="up u3">
            {(!polls || polls.length === 0) && (
              <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>رای‌گیری‌ای ساخته نشده</div>
            )}
            {polls && polls.map(p => (
              <div className="card poll" key={p.id}>
                <div className="poll-q">
                  {p.question}
                  <span className={`poll-status ${p.status}`}>{p.status === 'open' ? 'باز' : 'بسته'}</span>
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--mid)', marginBottom: 8 }}>
                  {p.total_votes.toLocaleString('fa-IR')} رای — {p.options.join(' · ')}
                </div>
                {p.status === 'open' && (
                  <button className="btn ghost" style={{ padding: 10, fontSize: 12 }} onClick={() => closePoll(p.id)}>بستن رای‌گیری</button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'admins' && isFull && (
        <>
          <div className="sect up u2">مدیریت ادمین‌ها</div>
          <div className="card up u2">
            <label className="f" style={{ marginTop: 0 }}>افزودن ادمین محدود (فقط لشکرکشی‌ها، روایت جنگ و مقام‌ها)</label>
            <PlayerPicker value={newAdminTarget} onChange={setNewAdminTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={addAdmin}>افزودن ادمین</button>
          </div>
          <div className="card up u2">
            {(!admins || admins.length === 0) && (
              <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>ادمینی نیست</div>
            )}
            {admins && admins.map(a => (
              <div className="res" key={a.tg_id}>
                <div className="ic"><Shield s={16} /></div>
                <div className="n">{a.name || a.tg_id}<small>{a.role === 'full' ? 'ادمین کامل' : 'ادمین محدود'}{a.castle ? ` · ${a.castle}` : ''}</small></div>
                {a.role === 'limited' && (
                  <button className="btn ghost" style={{ width: 'auto', padding: '8px 12px', fontSize: 11.5 }} onClick={() => removeAdmin(a.tg_id)}>حذف</button>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
