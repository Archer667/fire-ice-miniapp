import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Shield, Plus, Close } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { WARDEN_GROUPS, REGIONS_STATIC } from '../gamedata.js';

export default function Admin() {
  const { me, toast } = useGame();
  const isFull = me.admin_role === 'full';

  const [pending, setPending] = useState(null);
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
  const [busy, setBusy] = useState(false);

  const loadPending = () => api.adminPending().then(setPending).catch(e => toast(e.message));
  const loadPolls = () => api.polls().then(setPolls).catch(e => toast(e.message));
  const loadAdmins = () => api.adminListAdmins().then(setAdmins).catch(e => toast(e.message));

  useEffect(() => {
    loadPending();
    loadPolls();
    if (isFull) loadAdmins();
  }, []);

  const verdict = async (id, action) => {
    setBusy(true);
    try {
      await api.adminVerdict(id, action, action === 'approve' ? 'تایید شد' : 'رد شد', 0);
      haptic('medium');
      toast(action === 'approve' ? 'سناریو تایید شد' : 'سناریو رد شد');
      loadPending();
    } catch (e) { toast(e.message); }
    setBusy(false);
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
      <div className="page-sub up">{isFull ? 'ادمین کامل' : 'ادمین محدود — فقط سناریوها و مقام‌ها'}</div>

      <div className="sect up u1">سناریوهای در انتظار</div>
      <div className="up u1">
        {(!pending || pending.length === 0) && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>سناریوی در انتظاری نیست</div>
        )}
        {pending && pending.map(s => (
          <div className="card" key={s.id} style={{ marginBottom: 10 }}>
            <div className="res">
              <div className="ic"><Shield s={16} /></div>
              <div className="n">{s.player}<small>{s.op_type} · {s.from} ← {s.to} · {s.cost.toLocaleString('fa-IR')} طلا</small></div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--mid)', margin: '8px 0', lineHeight: 1.8 }}>{s.plan}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn" style={{ padding: 11 }} disabled={busy} onClick={() => verdict(s.id, 'approve')}>تایید</button>
              <button className="btn ghost" style={{ padding: 11 }} disabled={busy} onClick={() => verdict(s.id, 'reject')}>رد</button>
            </div>
          </div>
        ))}
      </div>

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

      <div className="sect up u2">تعیین پادشاه/ملکه</div>
      <div className="card up u2">
        <label className="f" style={{ marginTop: 0 }}>لرد (باید الان یکی از سه والی باشد)</label>
        <PlayerPicker value={kingTarget} onChange={setKingTarget} single />
        <button className="btn" style={{ marginTop: 14 }} onClick={setKing}>ثبت پادشاه/ملکه</button>
      </div>

      <div className="sect up u2">تعیین عنوان (لقب)</div>
      <div className="card up u2">
        <label className="f" style={{ marginTop: 0 }}>لرد</label>
        <PlayerPicker value={epithetTarget} onChange={setEpithetTarget} single />
        <label className="f">عنوان تازه</label>
        <input value={epithetText} onChange={e => setEpithetText(e.target.value)} placeholder="مثلاً: شکنندهٔ زنجیرها" />
        <button className="btn" style={{ marginTop: 14 }} onClick={setEpithet}>ثبت عنوان</button>
      </div>

      {isFull && (
        <>
          <div className="sect up u3">رای‌گیری تازه</div>
          <div className="card up u3">
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

          <div className="sect up u3">مدیریت ادمین‌ها</div>
          <div className="card up u3">
            <label className="f" style={{ marginTop: 0 }}>افزودن ادمین محدود (فقط سناریوها و مقام‌ها)</label>
            <PlayerPicker value={newAdminTarget} onChange={setNewAdminTarget} single />
            <button className="btn" style={{ marginTop: 14 }} onClick={addAdmin}>افزودن ادمین</button>
          </div>
          <div className="card up u3">
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
