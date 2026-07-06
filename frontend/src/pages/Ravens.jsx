import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Send, Plus, Back } from '../components/Icons.jsx';

export default function Ravens() {
  const { toast } = useGame();
  const [inbox, setInbox] = useState(null);
  const [openWith, setOpenWith] = useState(null);   // نام لرد
  const [thread, setThread] = useState([]);
  const [text, setText] = useState('');
  const [composeTo, setComposeTo] = useState('');
  const [composing, setComposing] = useState(false);

  const loadInbox = () => api.inbox().then(setInbox).catch(e => toast(e.message));
  useEffect(() => { loadInbox(); }, []);

  const openThread = async (name) => {
    haptic();
    setOpenWith(name);
    try { setThread(await api.thread(name)); } catch (e) { toast(e.message); }
  };

  const send = async () => {
    const t = text.trim();
    if (!t) return;
    try {
      // ارسال با نامِ لرد: backend قلعه می‌خواهد؛ در نسخهٔ ساده نام قلعه = ورودی compose
      await api.sendRaven({ to_castle: composing ? composeTo.trim() : openWith, text: t });
      haptic('medium');
      setThread(prev => [...prev, { mine: true, text: t }]);
      setText('');
      if (composing) { setComposing(false); toast('کلاغ پر کشید'); loadInbox(); }
    } catch (e) { toast(e.message); }
  };

  /* ---------- نمای گفتگو ---------- */
  if (openWith || composing) return (
    <>
      <div className="back up" onClick={() => { setOpenWith(null); setComposing(false); loadInbox(); }}>
        <Back s={15} /> بازگشت به صندوق نامه
      </div>
      {composing ? (
        <>
          <div className="page-title up">کلاغ تازه</div>
          <div className="page-sub up">نام قلعهٔ گیرنده را بنویس — کلاغ راهش را بلد است</div>
          <div className="card up u1">
            <label className="f" style={{ marginTop: 0 }}>قلعهٔ گیرنده</label>
            <input value={composeTo} onChange={e => setComposeTo(e.target.value)} placeholder="مثلاً: کسترلی راک" />
          </div>
        </>
      ) : (
        <div className="page-title up">{openWith}</div>
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
  return (
    <>
      <div className="page-title up">کلاغ‌ها</div>
      <div className="page-sub up">نامه‌های خصوصی میان تو و لردهای وستروس</div>
      <div className="up u1">
        {inbox.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
            هنوز کلاغی برایت نیامده — تو اولین نامه را بفرست
          </div>
        )}
        {inbox.map((m, i) => (
          <div key={i} className="mailrow" onClick={() => openThread(m.with_name)}>
            <div className="mava">{m.with_name.charAt(0)}</div>
            <div className="mt">
              <div className="mn">{m.with_name}{m.unread > 0 && <span className="dot" />}</div>
              <div className="ms">{m.last_text}</div>
            </div>
          </div>
        ))}
      </div>
      <button className="fab" onClick={() => { haptic(); setComposing(true); setThread([]); }}>
        <Plus s={22} />
      </button>
    </>
  );
}
