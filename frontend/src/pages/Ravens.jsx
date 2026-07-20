import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Send, Plus, Back, Eye } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';

const SYSTEM_TG_ID = 0;

function timeAgo(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 60) return `${min.toLocaleString('fa-IR')} دقیقه پیش`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h.toLocaleString('fa-IR')} ساعت پیش`;
  return `${Math.floor(h / 24).toLocaleString('fa-IR')} روز پیش`;
}

export default function Ravens() {
  const { toast, refreshUnread } = useGame();
  const [inbox, setInbox] = useState(null);
  const [tab, setTab] = useState('announcements');
  const [openWith, setOpenWith] = useState(null);   // {tg_id, name}
  const [thread, setThread] = useState([]);
  const [text, setText] = useState('');
  const [composeTargets, setComposeTargets] = useState([]);
  const [composing, setComposing] = useState(false);
  const [rumors, setRumors] = useState(null);

  const loadInbox = () => api.inbox().then(setInbox).catch(e => { toast(e.message); setInbox([]); });
  const loadRumors = () => api.listRumors().then(setRumors).catch(e => { toast(e.message); setRumors([]); });
  useEffect(() => { loadInbox(); }, []);
  useEffect(() => { if (tab === 'rumors' && rumors === null) loadRumors(); }, [tab]);

  const openThread = async (m) => {
    haptic();
    setOpenWith({ tg_id: m.with_tg_id, name: m.with_name });
    try {
      setThread(await api.thread(m.with_name));
      refreshUnread();
    } catch (e) { toast(e.message); }
  };

  const send = async () => {
    const t = text.trim();
    if (!t) return;
    const toTgIds = composing ? composeTargets.map(p => p.tg_id) : [openWith.tg_id];
    if (!toTgIds.length) { toast('حداقل یک گیرنده انتخاب کن'); return; }
    try {
      await api.sendRaven(toTgIds, t);
      haptic('medium');
      if (!composing) setThread(prev => [...prev, { mine: true, text: t }]);
      setText('');
      if (composing) {
        setComposing(false); setComposeTargets([]);
        toast(toTgIds.length > 1 ? `کلاغ برای ${toTgIds.length.toLocaleString('fa-IR')} لرد پر کشید` : 'کلاغ پر کشید');
        loadInbox();
      }
    } catch (e) { toast(e.message); }
  };

  /* ---------- نمای گفتگو ---------- */
  if (openWith || composing) return (
    <>
      <button type="button" className="rbtn back up" style={{ width: 'auto' }}
              onClick={() => { setOpenWith(null); setComposing(false); setComposeTargets([]); loadInbox(); }}>
        <Back s={15} /> بازگشت به صندوق نامه
      </button>
      {composing ? (
        <>
          <div className="page-title up">کلاغ تازه</div>
          <div className="page-sub up">یک یا چند لرد را جست‌وجو و انتخاب کن — کلاغ راهش را بلد است</div>
          <div className="card up u1">
            <label className="f" style={{ marginTop: 0 }}>گیرنده(ها)</label>
            <PlayerPicker value={composeTargets} onChange={setComposeTargets} />
          </div>
        </>
      ) : (
        <div className="page-title up">{openWith.name}</div>
      )}
      <div className="thread up u1" style={{ marginTop: 12 }}>
        {thread.map((m, i) => (
          <div key={i} className={`tmsg ${m.mine ? 'mine' : 'theirs'}`}>{m.text}</div>
        ))}
      </div>
      <div className="composer up u2">
        <input value={text} onChange={e => setText(e.target.value)}
               onKeyDown={e => e.key === 'Enter' && send()} placeholder="نامه‌ات را بنویس..." />
        <button type="button" aria-label="ارسال" onClick={send}><Send s={18} /></button>
      </div>
    </>
  );

  /* ---------- صندوق نامه ---------- */
  if (!inbox) return <div className="loading">کلاغ‌ها در راه‌اند...</div>;

  const announcements = inbox.filter(m => m.with_tg_id === SYSTEM_TG_ID);
  const personal = inbox.filter(m => m.with_tg_id !== SYSTEM_TG_ID);
  const rows = tab === 'announcements' ? announcements : personal;

  return (
    <>
      <div className="page-title up">کلاغ‌ها</div>
      <div className="page-sub up">نامه‌های خصوصی و اطلاعیه‌های شورای جنگ</div>

      <div className="tabs up u1" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'announcements'}
                className={`rbtn tab ${tab === 'announcements' ? 'on' : ''}`} onClick={() => { haptic(); setTab('announcements'); }}>
          اطلاعیه‌ها{announcements.some(m => m.unread > 0) ? ' •' : ''}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'messages'}
                className={`rbtn tab ${tab === 'messages' ? 'on' : ''}`} onClick={() => { haptic(); setTab('messages'); }}>
          پیام‌ها{personal.some(m => m.unread > 0) ? ' •' : ''}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'rumors'}
                className={`rbtn tab ${tab === 'rumors' ? 'on' : ''}`} onClick={() => { haptic(); setTab('rumors'); }}>
          شایعات
        </button>
      </div>

      {tab !== 'rumors' && (
        <div className="up u2">
          {rows.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
              {tab === 'announcements' ? 'هنوز اطلاعیه‌ای نیامده' : 'هنوز کلاغی برایت نیامده — تو اولین نامه را بفرست'}
            </div>
          )}
          {rows.map((m, i) => (
            <button type="button" key={i} className="rbtn mailrow" onClick={() => openThread(m)}>
              <div className="mava">{m.with_name.charAt(0)}</div>
              <div className="mt">
                <div className="mn">{m.with_name}{m.unread > 0 && <span className="dot" />}</div>
                <div className="ms">{m.last_text}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {tab === 'rumors' && (
        <div className="up u2">
          {rumors === null && <div className="loading">در حال بارگذاری...</div>}
          {rumors && rumors.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز شایعه‌ای پخش نشده</div>
          )}
          {rumors && rumors.map(r => (
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
      )}

      {tab === 'messages' && (
        <button type="button" className="fab" aria-label="کلاغ تازه" onClick={() => { haptic(); setComposing(true); setThread([]); }}>
          <Plus s={22} />
        </button>
      )}
    </>
  );
}
