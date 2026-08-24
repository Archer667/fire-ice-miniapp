import { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Wine, Heart, Crown, Scroll, Coin } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { REGIONS_STATIC, ALLIANCE_TYPES, PRIVATE_ALLIANCE_MULTIPLIER, WARDEN_GROUPS, FEAST_COST, SMALL_COUNCIL_SEATS } from '../gamedata.js';

const STATUS_FA = {
  pending: 'در انتظار پاسخ', accepted: 'برقرار', rejected: 'رد شده',
  dissolved: 'منحل‌شده (ادمین)', broken: 'باطل‌شده (خیانت)', left: 'ترک‌شده',
};
const TABS = [
  { key: 'main',      label: 'دیپلماسی' },
  { key: 'alliances', label: 'اتحادها' },
  { key: 'polls',     label: 'رای‌گیری' },
];
const ALLIANCE_SEEN_KEY = 'valeria_public_alliances_seen';
const loadSeenAllianceIds = () => { try { return new Set(JSON.parse(localStorage.getItem(ALLIANCE_SEEN_KEY)) || []); } catch { return new Set(); } };
const TRIBUTE_STATUS_FA = { pending: 'در انتظار پرداخت', paid: 'پرداخت‌شده', expired: 'منقضی (پرداخت نشد)' };
function hoursLeft(dueAt) {
  return Math.max(0, Math.round((new Date(dueAt).getTime() - Date.now()) / 3600000));
}

export default function Diplomacy() {
  const { me, setMe, toast } = useGame();
  const [tab, setTab] = useState('main');
  const [titles, setTitles] = useState(null);
  const [alliances, setAlliances] = useState(null);
  const [publicAlliances, setPublicAlliances] = useState(null);
  const [seenAllianceIds, setSeenAllianceIds] = useState(loadSeenAllianceIds);
  const [polls, setPolls] = useState(null);
  const [targets, setTargets] = useState([]);
  const [type, setType] = useState('non_aggression');
  const [pactName, setPactName] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [penaltyGold, setPenaltyGold] = useState(500);
  const [busy, setBusy] = useState(false);
  const [respondBusyId, setRespondBusyId] = useState(null);
  const [feastBusy, setFeastBusy] = useState(false);
  const [councilSeat, setCouncilSeat] = useState(Object.keys(SMALL_COUNCIL_SEATS)[0]);
  const [councilTarget, setCouncilTarget] = useState([]);
  const [councilBusy, setCouncilBusy] = useState(false);
  const [tribute, setTribute] = useState(null);
  const [demandTargetId, setDemandTargetId] = useState('');
  const [demandAmount, setDemandAmount] = useState('');
  const [demandBusy, setDemandBusy] = useState(false);
  const [payBusyId, setPayBusyId] = useState(null);
  const [salaryDrafts, setSalaryDrafts] = useState({});
  const [kingSalaryDraft, setKingSalaryDraft] = useState('');

  const load = () => {
    api.titles().then(setTitles).catch(e => toast(e.message));
    api.diplomacyMine().then(setAlliances).catch(e => toast(e.message));
    api.diplomacyPublic().then(setPublicAlliances).catch(e => toast(e.message));
    api.polls().then(setPolls).catch(e => toast(e.message));
    api.tributeMine().then(setTribute).catch(e => toast(e.message));
  };
  useEffect(() => { load(); }, []);

  const newAllianceCount = useMemo(
    () => (publicAlliances || []).filter(a => !seenAllianceIds.has(a.id)).length,
    [publicAlliances, seenAllianceIds]
  );

  const openTab = (key) => {
    setTab(key);
    if (key !== 'alliances' || !publicAlliances?.length) return;
    const next = new Set(seenAllianceIds);
    publicAlliances.forEach(a => next.add(a.id));
    setSeenAllianceIds(next);
    localStorage.setItem(ALLIANCE_SEEN_KEY, JSON.stringify([...next]));
  };

  useEffect(() => {
    if (tribute?.demand_targets?.length && !demandTargetId) {
      setDemandTargetId(String(tribute.demand_targets[0].tg_id));
    }
  }, [tribute]);

  useEffect(() => {
    if (!titles?.council_salary_rates) return;
    setSalaryDrafts(prev => {
      const next = { ...prev };
      for (const seat of Object.keys(SMALL_COUNCIL_SEATS)) {
        if (next[seat] === undefined) next[seat] = String(titles.council_salary_rates[seat] || 0);
      }
      return next;
    });
  }, [titles]);

  useEffect(() => {
    if (titles && kingSalaryDraft === '') setKingSalaryDraft(String(titles.king_salary_gold || 0));
  }, [titles]);

  const castVote = async (pollId, option) => {
    try {
      const updated = await api.vote(pollId, option);
      haptic('medium');
      setPolls(prev => prev.map(p => p.id === pollId ? updated : p));
    } catch (e) { toast(e.message); }
  };

  const doFeast = async () => {
    setFeastBusy(true);
    try {
      const res = await api.feast();
      haptic('medium');
      setMe({
        ...me,
        popularity: res.popularity,
        resources: { ...me.resources, wine: me.resources.wine - FEAST_COST.wine, food: me.resources.food - FEAST_COST.food },
      });
      toast('ضیافت برگزار شد — محبوبیت بالا رفت');
    } catch (e) { toast(e.message); }
    setFeastBusy(false);
  };

  const unitCost = ALLIANCE_TYPES[type].wine_cost * (isPrivate ? PRIVATE_ALLIANCE_MULTIPLIER : 1);

  const propose = async () => {
    if (targets.length === 0) { toast('حداقل یک لرد را برای پیشنهاد انتخاب کن'); return; }
    if (type === 'non_aggression' && (!penaltyGold || penaltyGold <= 0)) { toast('مقدار غرامتِ خیانت را مشخص کن'); return; }
    setBusy(true);
    try {
      const res = await api.diplomacyPropose(targets.map(t => t.tg_id), type, pactName.trim(), isPrivate, type === 'non_aggression' ? penaltyGold : 0);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, wine: me.resources.wine - unitCost * (res.sent_to || targets.length) } });
      toast(`پیشنهاد پیمان با کلاغ به ${res.sent_to || targets.length} لرد ارسال شد`);
      setTargets([]); setPactName(''); setIsPrivate(false);
      load();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  const respond = async (id, accept) => {
    if (respondBusyId) return;
    setRespondBusyId(id);
    try {
      await api.diplomacyRespond(id, accept);
      haptic('medium');
      toast(accept ? 'پیمان پذیرفته شد' : 'پیمان رد شد');
      load();
    } catch (e) { toast(e.message); }
    setRespondBusyId(null);
  };

  const leaveAlliance = async (alliance) => {
    if (respondBusyId) return;
    const penalty = alliance.type === 'non_aggression' ? (alliance.penalty_gold || 0) : 0;
    if (penalty && !window.confirm(`برای ترک این پیمان باید ${penalty.toLocaleString('fa-IR')} سکه غرامت بدهی. ادامه می‌دهی؟`)) return;
    setRespondBusyId(alliance.id);
    try {
      await api.diplomacyLeave(alliance.id);
      haptic('medium');
      toast(penalty ? `از پیمان خارج شدی و ${penalty.toLocaleString('fa-IR')} سکه غرامت پرداخت شد` : 'از پیمان خارج شدی');
      load();
    } catch (e) { toast(e.message); }
    setRespondBusyId(null);
  };

  const assignCouncil = async () => {
    if (!councilTarget.length) { toast('یک لرد را انتخاب کن'); return; }
    setCouncilBusy(true);
    try {
      await api.setSmallCouncil(councilSeat, councilTarget[0].tg_id);
      haptic('medium');
      toast('کرسی شورای کوچک واگذار شد');
      setCouncilTarget([]);
      load();
    } catch (e) { toast(e.message); }
    setCouncilBusy(false);
  };

  const clearCouncilSeat = async (seat) => {
    try {
      await api.setSmallCouncil(seat, null);
      haptic();
      toast('این کرسی خالی شد');
      load();
    } catch (e) { toast(e.message); }
  };

  const saveCouncilSalary = async (seat) => {
    const amount = parseInt(salaryDrafts[seat], 10);
    if (!Number.isFinite(amount) || amount < 0) { toast('مبلغ را درست وارد کن'); return; }
    try {
      await api.setCouncilSalary(seat, amount);
      haptic('medium');
      toast('حقوقِ این کرسی ثبت شد');
      load();
    } catch (e) { toast(e.message); }
  };

  const saveKingSalary = async () => {
    const amount = parseInt(kingSalaryDraft, 10);
    if (!Number.isFinite(amount) || amount < 0) { toast('مبلغ را درست وارد کن'); return; }
    try {
      await api.setKingSalary(amount);
      haptic('medium');
      toast('حقوقِ روزانه‌ات ثبت شد');
      load();
    } catch (e) { toast(e.message); }
  };

  const demandTribute = async () => {
    const amount = parseInt(demandAmount, 10);
    if (!demandTargetId) { toast('یک نفر را انتخاب کن'); return; }
    if (!Number.isFinite(amount) || amount <= 0) { toast('مبلغ را درست وارد کن'); return; }
    setDemandBusy(true);
    try {
      await api.demandTribute(parseInt(demandTargetId, 10), amount);
      haptic('medium');
      toast('خراج با کلاغ درخواست شد — ۲۴ ساعت مهلت دارد');
      setDemandAmount('');
      load();
    } catch (e) { toast(e.message); }
    setDemandBusy(false);
  };

  const payTribute = async (id) => {
    setPayBusyId(id);
    try {
      const owed = tribute.owed.find(t => t.id === id);
      await api.payTribute(id);
      haptic('medium');
      toast('خراج پرداخت شد');
      setMe({ ...me, resources: { ...me.resources, gold: me.resources.gold - owed.amount } });
      load();
    } catch (e) { toast(e.message); }
    setPayBusyId(null);
  };

  return (
    <>
      <div className="page-title up">دیپلماسی</div>
      <div className="page-sub up">ضیافت بگیر، پیمان ببند، ببین قدرت دست کیه</div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); openTab(t.key); }}>
            {t.label}
            {t.key === 'alliances' && newAllianceCount > 0 && (
              <span className="tab-count-badge">{newAllianceCount.toLocaleString('fa-IR')}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'main' && (
      <>
      <div className="sect up u2">ضیافت</div>
      <div className="card up u2">
        <div className="res">
          <div className="ic"><Wine s={18} /></div>
          <div className="n">برگزاری ضیافت<small>{FEAST_COST.wine.toLocaleString('fa-IR')} شراب + {FEAST_COST.food.toLocaleString('fa-IR')} غذا → محبوبیت بیشتر</small></div>
        </div>
        <button className="btn ghost bld-btn" disabled={feastBusy} onClick={doFeast}>
          {feastBusy ? 'در حال برگزاری...' : 'برگزاری ضیافت'}
        </button>
      </div>

      <div className="sect up u2">پیشنهاد پیمان تازه</div>
      <div className="card up u2">
        <label className="f" style={{ marginTop: 0 }}>نام پیمان</label>
        <input value={pactName} onChange={e => setPactName(e.target.value)} maxLength={60} placeholder="مثلاً «پیمان دو اژدها» — اختیاری" />
        <label className="f">لرد(ها)ی طرف مقابل</label>
        <PlayerPicker value={targets} onChange={setTargets} />
        <label className="f">نوع پیمان</label>
        <select value={type} onChange={e => setType(e.target.value)}>
          {Object.entries(ALLIANCE_TYPES).map(([id, t]) => (
            <option key={id} value={id}>{t.name} — {t.wine_cost.toLocaleString('fa-IR')} شراب هرکدام</option>
          ))}
        </select>
        {type === 'non_aggression' && (
          <>
            <label className="f">غرامتِ خیانت (طلا)</label>
            <input type="number" min={1} value={penaltyGold}
                   onChange={e => setPenaltyGold(Math.max(0, parseInt(e.target.value, 10) || 0))}
                   placeholder="مثلاً ۵۰۰" />
            <div className="page-sub" style={{ margin: '4px 4px 0' }}>
              اگه یکی از طرفین با وجود این پیمان به اون یکی حمله/غارت/محاصره کنه، همین مقدار طلا
              (یا اگه طلا کم بود، به همون میزان از امتیازش) ازش کم می‌شه.
            </div>
          </>
        )}
        <label className="f">نمایش در تب عمومیِ «اتحادها»</label>
        <div className="grid2" role="radiogroup" aria-label="نمایش عمومی">
          <button type="button" role="radio" aria-checked={!isPrivate}
                  className={`rbtn pick ${!isPrivate ? 'sel' : ''}`} onClick={() => { haptic(); setIsPrivate(false); }}>
            <div className="n">عمومی</div>
            <div className="c">همه می‌بینن</div>
          </button>
          <button type="button" role="radio" aria-checked={isPrivate}
                  className={`rbtn pick ${isPrivate ? 'sel' : ''}`} onClick={() => { haptic(); setIsPrivate(true); }}>
            <div className="n">خصوصی</div>
            <div className="c">{PRIVATE_ALLIANCE_MULTIPLIER.toLocaleString('fa-IR')}× هزینه</div>
          </button>
        </div>
        <div className="page-sub" style={{ margin: '10px 4px 0' }}>
          هزینه به‌ازای هر لرد: <b style={{ color: 'var(--az2)' }}>{unitCost.toLocaleString('fa-IR')} شراب</b>
        </div>
        <button className="btn" style={{ marginTop: 14 }} disabled={busy} onClick={propose}>
          {busy ? 'در حال ارسال...' : `ارسال پیشنهاد با کلاغ${targets.length ? ` (${targets.length.toLocaleString('fa-IR')} نفر)` : ''}`}
        </button>
      </div>

      <div className="sect up u2">پیمان‌های من</div>
      <div className="card up u2">
        {(!alliances || alliances.length === 0) && (
          <div style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5, padding: '6px 0' }}>هنوز هیچ پیمانی نبسته‌ای</div>
        )}
        {alliances && alliances.map(a => (
          <div className="troop" key={a.id}>
            <div className="tn">
              {a.name ? <>{a.name} <small style={{ display: 'inline' }}>— {a.other_name}</small></> : a.other_name}
              <small>
                {a.type_name} · {STATUS_FA[a.status]}{a.mine_proposed ? ' · پیشنهاد تو' : ' · پیشنهاد او'}
                {a.public === false ? ' · خصوصی' : ''}
                {a.type === 'non_aggression' && a.penalty_gold ? ` · غرامت خیانت: ${a.penalty_gold.toLocaleString('fa-IR')} سکه` : ''}
              </small>
            </div>
            {!a.mine_proposed && a.status === 'pending' && (
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }} disabled={respondBusyId === a.id} onClick={() => respond(a.id, true)}>پذیرفتن</button>
                <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }} disabled={respondBusyId === a.id} onClick={() => respond(a.id, false)}>رد</button>
              </div>
            )}
            {(a.type === 'trade' || a.type === 'non_aggression') && a.status === 'accepted' && (
              <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }} disabled={respondBusyId === a.id} onClick={() => leaveAlliance(a)}>
                {a.type === 'non_aggression' ? `ترک با پرداخت ${(a.penalty_gold || 0).toLocaleString('fa-IR')} سکه` : 'ترک پیمان'}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="sect up u3">سلسله‌مراتب قدرت</div>
      <div className="card up u3">
        <div className="res">
          <div className="ic"><Crown s={18} /></div>
          <div className="n">پادشاه/ملکه<small>فقط از بین والی‌ها انتخاب می‌شه · حقوقِ روزانه {titles?.king_salary_gold?.toLocaleString('fa-IR')} سکه</small></div>
          <div className="val">{titles?.king ? titles.king.title + ' ' + titles.king.name : '—'}</div>
        </div>
        {titles?.is_king && (
          <div style={{ display: 'flex', gap: 6, margin: '0 0 10px' }}>
            <input type="number" min={0} value={kingSalaryDraft}
                   onChange={e => setKingSalaryDraft(e.target.value)}
                   placeholder="حقوقِ روزانهٔ خودت (سکه)" style={{ flex: 1 }} />
            <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }}
                    onClick={saveKingSalary}>ثبت</button>
          </div>
        )}
        {Object.entries(WARDEN_GROUPS).map(([gid, g]) => (
          <div className="res" key={gid}>
            <div className="ic"><Scroll s={18} /></div>
            <div className="n">{g.name}<small>{g.regions.map(r => REGIONS_STATIC[r]?.name).join(' · ')}</small></div>
            <div className="val">{titles?.wardens?.[gid] ? titles.wardens[gid].name : '—'}</div>
          </div>
        ))}
        <div className="res">
          <div className="ic"><Coin s={18} /></div>
          <div className="n">خزانهٔ رد کیپ<small>از خراجِ استاد سکه پر می‌شه، حقوقِ روزانه ازش پرداخت می‌شه</small></div>
          <div className="val">{(titles?.treasury_gold ?? 0).toLocaleString('fa-IR')} سکه</div>
        </div>
      </div>

      <div className="sect up u3">شورای کوچک</div>
      <div className="card up u3">
        {Object.entries(SMALL_COUNCIL_SEATS).map(([seat, label]) => {
          const holder = titles?.small_council?.[seat];
          const rate = titles?.council_salary_rates?.[seat] || 0;
          return (
            <div key={seat}>
              <div className="res">
                <div className="ic"><Scroll s={16} /></div>
                <div className="n">{label}<small>{holder ? holder.name : 'کرسی خالی'} · حقوقِ روزانه {rate.toLocaleString('fa-IR')} سکه</small></div>
                {titles?.is_king && holder && (
                  <button className="btn ghost" style={{ width: 'auto', padding: '7px 12px', fontSize: 11 }}
                          onClick={() => clearCouncilSeat(seat)}>خالی کن</button>
                )}
              </div>
              {titles?.is_king && (
                <div style={{ display: 'flex', gap: 6, margin: '0 0 10px' }}>
                  <input type="number" min={0} value={salaryDrafts[seat] ?? ''}
                         onChange={e => setSalaryDrafts(prev => ({ ...prev, [seat]: e.target.value }))}
                         placeholder="حقوقِ روزانه (سکه)" style={{ flex: 1 }} />
                  <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }}
                          onClick={() => saveCouncilSalary(seat)}>ثبت</button>
                </div>
              )}
            </div>
          );
        })}
        {titles?.is_king ? (
          <>
            <label className="f">کرسی</label>
            <select value={councilSeat} onChange={e => setCouncilSeat(e.target.value)}>
              {Object.entries(SMALL_COUNCIL_SEATS).map(([seat, label]) => <option key={seat} value={seat}>{label}</option>)}
            </select>
            <label className="f">لرد</label>
            <PlayerPicker value={councilTarget} onChange={setCouncilTarget} single />
            <button className="btn" style={{ marginTop: 14 }} disabled={councilBusy} onClick={assignCouncil}>
              {councilBusy ? 'در حال ثبت...' : 'انتصاب به این کرسی'}
            </button>
          </>
        ) : (
          <div className="page-sub" style={{ margin: '10px 4px 0' }}>فقط خودِ پادشاه/ملکهٔ فعلی می‌تواند شورای کوچک را بچیند</div>
        )}
      </div>

      <div className="sect up u3">بالادستیِ اقلیم من</div>
      <div className="card up u3">
        <div className="res">
          <div className="ic"><Heart s={18} /></div>
          <div className="n">{REGIONS_STATIC[me.region]?.name}<small>لرد/لیدی برتر این اقلیم</small></div>
          <div className="val">{titles?.overlords?.[me.region] ? titles.overlords[me.region].name : '—'}</div>
        </div>
      </div>

      {tribute?.owed?.length > 0 && (
        <>
          <div className="sect up u3">خراج‌هایی که باید بپردازم</div>
          <div className="card up u3">
            {tribute.owed.map(t => (
              <div className="troop" key={t.id}>
                <div className="tn">
                  {t.from_role_label} {t.from_name}
                  <small>{t.amount.toLocaleString('fa-IR')} سکه · {hoursLeft(t.due_at)} ساعت تا مهلت</small>
                </div>
                <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }}
                        disabled={payBusyId === t.id} onClick={() => payTribute(t.id)}>
                  {payBusyId === t.id ? 'در حال پرداخت...' : 'پرداخت'}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {tribute?.my_role && (
        <>
          <div className="sect up u3">خراج‌گیری ({tribute.my_role_label})</div>
          <div className="card up u3">
            {tribute.demand_targets.length === 0 ? (
              <div className="page-sub" style={{ margin: '0 4px' }}>هنوز زیردستِ مستقیمی نداری تا ازش خراج بخوای</div>
            ) : (
              <>
                <label className="f" style={{ marginTop: 0 }}>از چه کسی</label>
                <select value={demandTargetId} onChange={e => setDemandTargetId(e.target.value)}>
                  {tribute.demand_targets.map(p => <option key={p.tg_id} value={p.tg_id}>{p.name}</option>)}
                </select>
                <label className="f">مبلغ (طلا)</label>
                <input type="number" min={1} value={demandAmount}
                       onChange={e => setDemandAmount(e.target.value)} placeholder="مثلاً ۵۰۰" />
                <div className="page-sub" style={{ margin: '4px 4px 0' }}>
                  ۲۴ ساعت مهلت داره. اگه نده هیچ پیامدِ خودکاری نیست — فقط یه کلاغ برات میاد که بگه پرداخت نشد.
                </div>
                <button className="btn" style={{ marginTop: 14 }} disabled={demandBusy} onClick={demandTribute}>
                  {demandBusy ? 'در حال ارسال...' : 'درخواستِ خراج با کلاغ'}
                </button>
              </>
            )}
          </div>
        </>
      )}

      {tribute?.demanded?.length > 0 && (
        <>
          <div className="sect up u3">خراج‌هایی که خواسته‌ام</div>
          <div className="card up u3">
            {tribute.demanded.map(t => (
              <div className="res" key={t.id}>
                <div className="ic"><Coin s={16} /></div>
                <div className="n">{t.to_name}<small>{t.amount.toLocaleString('fa-IR')} سکه · {TRIBUTE_STATUS_FA[t.status]}</small></div>
              </div>
            ))}
          </div>
        </>
      )}
      </>
      )}

      {tab === 'alliances' && (
        <div className="up u2">
          <div className="page-sub" style={{ margin: '0 4px 10px' }}>
            همهٔ اتحادهای برقرارِ عمومیِ وستروس — پیمان‌های خصوصی اینجا نشان داده نمی‌شوند
          </div>
          {(!publicAlliances || publicAlliances.length === 0) && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز اتحاد عمومی‌ای برقرار نشده</div>
          )}
          {publicAlliances && publicAlliances.map(a => (
            <div className="card" key={a.id} style={{ marginBottom: 10 }}>
              <div className="res">
                <div className="ic"><Crown s={16} /></div>
                <div className="n">
                  {a.name || `${a.from_name} و ${a.to_name}`}
                  <small>{a.type_name}{a.name ? ` · ${a.from_name} و ${a.to_name}` : ''}</small>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'polls' && (
        <div className="up u2">
          {(!polls || polls.length === 0) && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              فعلاً هیچ رای‌گیری‌ای باز نیست — هروقت ادمین یکی باز کنه، همین‌جا می‌بینیش
            </div>
          )}
          {polls && polls.map(p => (
            <div className="card poll" key={p.id}>
              <div className="poll-q">
                {p.question}
                <span className={`poll-status ${p.status}`}>{p.status === 'open' ? 'باز' : 'بسته'}</span>
              </div>
              {p.options.map((opt, i) => {
                const pct = p.total_votes ? Math.round((p.tally[i] / p.total_votes) * 100) : 0;
                const mine = p.my_vote === i;
                const canVote = p.status === 'open' && p.eligible;
                return (
                  <div key={i} className={`poll-opt ${mine ? 'mine' : ''}`}
                       onClick={() => canVote && castVote(p.id, i)} style={canVote ? {} : { cursor: 'default' }}>
                    <div className="poll-opt-bar"><i style={{ width: pct + '%' }} /></div>
                    <div className="poll-opt-row">
                      <span>{opt}{mine ? ' ✓' : ''}</span>
                      <span>{pct}٪ ({p.tally[i].toLocaleString('fa-IR')})</span>
                    </div>
                  </div>
                );
              })}
              {!p.eligible && p.status === 'open' && (
                <div className="poll-note">این یکی رو نمی‌تونی رای بدی — فقط نتیجه‌اش رو می‌بینی</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
