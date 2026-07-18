import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { ROLEPLAY_CATEGORIES } from '../gamedata.js';

const TABS = [
  { key: 'send',    label: 'ارسال رول' },
  { key: 'results', label: 'نتایج' },
];

export default function Roleplay() {
  const { toast } = useGame();
  const [tab, setTab] = useState('send');
  const [category, setCategory] = useState(Object.keys(ROLEPLAY_CATEGORIES)[0]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState(null);

  const load = () => api.roleplayMine().then(setRows).catch(e => { toast(e.message); setRows([]); });
  useEffect(() => { load(); }, []);

  const textTooShort = text.trim().length < 10;

  const send = async () => {
    if (textTooShort) { toast('رول را کمی بیشتر توضیح بده'); return; }
    setBusy(true);
    try {
      await api.sendRoleplay(category, text.trim());
      haptic('medium');
      toast('رول برای بررسی شورای جنگ فرستاده شد');
      setText('');
      load();
      setTab('results');
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <>
      <div className="page-title up">رول‌ها</div>
      <div className="page-sub up">یک سناریوی آزاد بنویس و بفرست — شورای جنگ می‌خواند و نتیجه‌اش را برایت می‌فرستد</div>

      <div className="tabs up u1" role="tablist">
        {TABS.map(t => (
          <button type="button" key={t.key} role="tab" aria-selected={tab === t.key}
               className={`rbtn tab ${tab === t.key ? 'on' : ''}`}
               onClick={() => { haptic(); setTab(t.key); }}>{t.label}</button>
        ))}
      </div>

      {tab === 'send' && (
        <div className="card up u2">
          <label className="f" style={{ marginTop: 0 }}>دسته‌بندی</label>
          <select value={category} onChange={e => setCategory(e.target.value)}>
            {Object.entries(ROLEPLAY_CATEGORIES).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          <label className="f">متن رول</label>
          <textarea value={text} onChange={e => setText(e.target.value)}
                    placeholder="سناریوت را بنویس... چه می‌کنی، چطور، و هدفت چیست؟" />

          <button className="btn" style={{ marginTop: 14 }} disabled={textTooShort || busy} onClick={send}>
            {busy ? 'در حال ارسال...' : 'ارسال رول به شورای جنگ'}
          </button>
        </div>
      )}

      {tab === 'results' && (
        <div className="up u2">
          {(!rows || rows.length === 0) && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز رولی نفرستاده‌ای</div>
          )}
          {rows && rows.map(r => (
            <div className="card" key={r.id} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="title-tag" style={{ marginInlineStart: 0 }}>{r.category_name}</span>
                <span className={`poll-status ${r.resolved ? '' : 'open'}`}>{r.resolved ? 'پاسخ آمد' : 'در انتظار بررسی'}</span>
              </div>
              <div style={{ marginTop: 10, fontSize: 12.5, lineHeight: 1.8, color: 'var(--mid)' }}>{r.text}</div>
              {r.resolved && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(160,195,255,0.07)', fontSize: 12.5, lineHeight: 1.8, color: 'var(--hi)' }}>
                  {r.result}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
