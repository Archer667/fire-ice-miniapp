import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import PlayerPicker from '../components/PlayerPicker.jsx';
import { Eye } from '../components/Icons.jsx';
import { RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE } from '../gamedata.js';

function timeAgo(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 60) return `${min.toLocaleString('fa-IR')} دقیقه پیش`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h.toLocaleString('fa-IR')} ساعت پیش`;
  return `${Math.floor(h / 24).toLocaleString('fa-IR')} روز پیش`;
}

export default function Rumors() {
  const { me, setMe, toast } = useGame();
  const [rows, setRows] = useState(null);
  const [target, setTarget] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  const load = () => api.listRumors().then(setRows).catch(e => { toast(e.message); setRows([]); });
  useEffect(() => { load(); }, []);

  const textTooShort = text.trim().length < 10;
  const overGold = (me.resources?.gold ?? 0) < RUMOR_GOLD_COST;

  const send = async () => {
    if (!target.length) { toast('یک لرد را هدف بگیر'); return; }
    if (textTooShort) { toast('شایعه را کمی بیشتر توضیح بده'); return; }
    if (overGold) { toast('طلای کافی برای پخش این شایعه نداری'); return; }
    setBusy(true);
    try {
      await api.sendRumor(target[0].tg_id, text.trim());
      haptic('medium');
      setMe({ ...me, resources: { ...me.resources, gold: me.resources.gold - RUMOR_GOLD_COST } });
      toast(`شایعه علیه «${target[0].name}» پخش شد`);
      setTarget([]); setText('');
      load();
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <>
      <div className="page-title up">شایعات</div>
      <div className="page-sub up">کارزار عمومی علیه یک لرد — همه می‌بینند، محبوبیتش کمی افت می‌کند</div>

      <div className="sect up u1">راه‌انداختن شایعهٔ تازه</div>
      <div className="card up u1">
        <label className="f" style={{ marginTop: 0 }}>هدف</label>
        <PlayerPicker value={target} onChange={setTarget} single />
        <label className="f">متن شایعه</label>
        <textarea value={text} onChange={e => setText(e.target.value)}
                  placeholder="چه شایعه‌ای دربارهٔ این لرد پخش می‌کنی..." />
        <div className="page-sub" style={{ margin: '10px 4px 0' }}>
          هزینه: <b style={{ color: 'var(--az2)' }}>{RUMOR_GOLD_COST.toLocaleString('fa-IR')} طلا</b> ·
          {' '}اثر: <b style={{ color: 'var(--danger)' }}>−{RUMOR_POPULARITY_DAMAGE.toLocaleString('fa-IR')} محبوبیت هدف</b>
        </div>
        <button className="btn" style={{ marginTop: 14 }} disabled={busy} onClick={send}>
          {busy ? 'در حال پخش...' : 'پخش شایعه'}
        </button>
      </div>

      <div className="sect up u2">شایعات وستروس</div>
      <div className="up u2">
        {rows === null && <div className="loading">در حال بارگذاری...</div>}
        {rows && rows.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز شایعه‌ای پخش نشده</div>
        )}
        {rows && rows.map(r => (
          <div className="card" key={r.id} style={{ marginBottom: 10 }}>
            <div className="res">
              <div className="ic"><Eye s={16} /></div>
              <div className="n">
                علیه {r.target}
                <small>{r.mine ? 'از طرف تو' : `از طرف ${r.author}`} · {timeAgo(r.created_at)}</small>
              </div>
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.8, color: 'var(--hi)', marginTop: 8 }}>{r.text}</div>
          </div>
        ))}
      </div>
    </>
  );
}
