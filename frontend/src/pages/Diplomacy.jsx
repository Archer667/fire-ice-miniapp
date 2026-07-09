import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Wine, Heart, Crown, Scroll } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { REGIONS_STATIC, ALLIANCE_TYPES, WARDEN_GROUPS, FEAST_COST } from '../gamedata.js';

const STATUS_FA = { pending: 'در انتظار پاسخ', accepted: 'برقرار', rejected: 'رد شده' };

export default function Diplomacy() {
  const { me, setMe, toast } = useGame();
  const [titles, setTitles] = useState(null);
  const [alliances, setAlliances] = useState(null);
  const [polls, setPolls] = useState(null);
  const [targets, setTargets] = useState([]);
  const [type, setType] = useState('non_aggression');
  const [busy, setBusy] = useState(false);
  const [feastBusy, setFeastBusy] = useState(false);

  const load = () => {
    api.titles().then(setTitles).catch(e => toast(e.message));
    api.diplomacyMine().then(setAlliances).catch(e => toast(e.message));
    api.polls().then(setPolls).catch(e => toast(e.message));
  };
  useEffect(() => { load(); }, []);

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

  const propose = async () => {
    if (targets.length === 0) { toast('حداقل یک لرد را برای پیشنهاد انتخاب کن'); return; }
    setBusy(true);
    try {
      const res = await api.diplomacyPropose(targets.map(t => t.tg_id), type);
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, wine: me.resources.wine - ALLIANCE_TYPES[type].wine_cost * (res.sent_to || targets.length) } });
      toast(`پیشنهاد پیمان با کلاغ به ${res.sent_to || targets.length} لرد ارسال شد`);
      setTargets([]);
      load();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  const respond = async (id, accept) => {
    try {
      await api.diplomacyRespond(id, accept);
      haptic('medium');
      toast(accept ? 'پیمان پذیرفته شد' : 'پیمان رد شد');
      load();
    } catch (e) { toast(e.message); }
  };

  return (
    <>
      <div className="page-title up">دیپلماسی</div>
      <div className="page-sub up">ضیافت بگیر، پیمان ببند، ببین قدرت دست کیه</div>

      <div className="sect up u1">ضیافت</div>
      <div className="card up u1">
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
        <label className="f" style={{ marginTop: 0 }}>لرد(ها)ی طرف مقابل</label>
        <PlayerPicker value={targets} onChange={setTargets} />
        <label className="f">نوع پیمان</label>
        <select value={type} onChange={e => setType(e.target.value)}>
          {Object.entries(ALLIANCE_TYPES).map(([id, t]) => (
            <option key={id} value={id}>{t.name} — {t.wine_cost.toLocaleString('fa-IR')} شراب هرکدام</option>
          ))}
        </select>
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
              {a.other_name}
              <small>{a.type_name} · {STATUS_FA[a.status]}{a.mine_proposed ? ' · پیشنهاد تو' : ' · پیشنهاد او'}</small>
            </div>
            {!a.mine_proposed && a.status === 'pending' && (
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }} onClick={() => respond(a.id, true)}>پذیرفتن</button>
                <button className="btn ghost" style={{ width: 'auto', padding: '9px 14px' }} onClick={() => respond(a.id, false)}>رد</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="sect up u2">رای‌گیری</div>
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

      <div className="sect up u3">سلسله‌مراتب قدرت</div>
      <div className="card up u3">
        <div className="res">
          <div className="ic"><Crown s={18} /></div>
          <div className="n">پادشاه/ملکه<small>فقط از بین والی‌ها انتخاب می‌شه</small></div>
          <div className="val">{titles?.king ? titles.king.title + ' ' + titles.king.name : '—'}</div>
        </div>
        {Object.entries(WARDEN_GROUPS).map(([gid, g]) => (
          <div className="res" key={gid}>
            <div className="ic"><Scroll s={18} /></div>
            <div className="n">{g.name}<small>{g.regions.map(r => REGIONS_STATIC[r]?.name).join(' · ')}</small></div>
            <div className="val">{titles?.wardens?.[gid] ? titles.wardens[gid].name : '—'}</div>
          </div>
        ))}
      </div>

      <div className="sect up u3">بالادستیِ اقلیم من</div>
      <div className="card up u3">
        <div className="res">
          <div className="ic"><Heart s={18} /></div>
          <div className="n">{REGIONS_STATIC[me.region]?.name}<small>لرد/لیدی برتر این اقلیم</small></div>
          <div className="val">{titles?.overlords?.[me.region] ? titles.overlords[me.region].name : '—'}</div>
        </div>
      </div>
    </>
  );
}
