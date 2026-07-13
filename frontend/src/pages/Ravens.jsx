import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Send, Plus, Back } from '../components/Icons.jsx';
import PlayerPicker from '../components/PlayerPicker.jsx';

const SYSTEM_TG_ID = 0;

export default function Ravens() {
  const { toast, refreshUnread } = useGame();
  const [inbox, setInbox] = useState(null);
  const [tab, setTab] = useState('announcements');
  const [openWith, setOpenWith] = useState(null);   // {tg_id, name}
  const [thread, setThread] = useState([]);
  const [text, setText] = useState('');
  const [composeTargets, setComposeTargets] = useState([]);
  const [composing, setComposing] = useState(false);

  const loadInbox = () => api.inbox().then(setInbox).catch(e => { toast(e.message); setInbox([]); });
  useEffect(() => { loadInbox(); }, []);

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
      <div className="back up" onClick={() => { setOpenWith(null); setComposing(false); setComposeTargets([]); loadInbox(); }}>
        <Back s={15} /> بازگشت به صندوق نامه
      </div>
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
        <button onClick={send}><Send s={18} /></button>
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

      <div className="tabs up u1">
        <div className={`tab ${tab === 'announcements' ? 'on' : ''}`} onClick={() => { haptic(); setTab('announcements'); }}>
          اطلاعیه‌ها{announcements.some(m => m.unread > 0) ? ' •' : ''}
        </div>
        <div className={`tab ${tab === 'messages' ? 'on' : ''}`} onClick={() => { haptic(); setTab('messages'); }}>
          پیام‌ها{personal.some(m => m.unread > 0) ? ' •' : ''}
        </div>
      </div>

      <div className="up u2">
        {rows.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
            {tab === 'announcements' ? 'هنوز اطلاعیه‌ای نیامده' : 'هنوز کلاغی برایت نیامده — تو اولین نامه را بفرست'}
          </div>
        )}
        {rows.map((m, i) => (
          <div key={i} className="mailrow" onClick={() => openThread(m)}>
            <div className="mava">{m.with_name.charAt(0)}</div>
            <div className="mt">
              <div className="mn">{m.with_name}{m.unread > 0 && <span className="dot" />}</div>
              <div className="ms">{m.last_text}</div>
            </div>
          </div>
        ))}
      </div>
      {tab === 'messages' && (
        <button className="fab" onClick={() => { haptic(); setComposing(true); setThread([]); }}>
          <Plus s={22} />
        </button>
      )}
    </>
  );
}
