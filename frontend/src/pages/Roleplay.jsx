import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { ROLEPLAY_CATEGORIES } from '../gamedata.js';
import PlayerPicker from '../components/PlayerPicker.jsx';

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
  const [battles, setBattles] = useState(null);
  const [campaignId, setCampaignId] = useState('');
  const [sabotageTarget, setSabotageTarget] = useState([]);

  const load = () => api.roleplayMine().then(setRows).catch(e => { toast(e.message); setRows([]); });
  const loadBattles = () => api.warRoleplayEligible().then(rows => {
    setBattles(rows);
    setCampaignId(prev => rows.some(b => b.campaign_id === prev) ? prev : (rows[0]?.campaign_id || ''));
  }).catch(e => { toast(e.message); setBattles([]); });

  useEffect(() => { load(); }, []);
  useEffect(() => { if (category === 'war' && battles === null) loadBattles(); }, [category]);

  const isWar = category === 'war';
  const textTooShort = text.trim().length < 10;
  const noBattleChosen = isWar && !campaignId;
  const noSabotageTarget = category === 'sabotage' && sabotageTarget.length === 0;

  const send = async () => {
    if (textTooShort) { toast('رول را کمی بیشتر توضیح بده'); return; }
    if (noBattleChosen) { toast('یک نبرد را انتخاب کن'); return; }
    if (noSabotageTarget) { toast('لرد هدف خرابکاری را مشخص کن'); return; }
    setBusy(true);
    try {
      const sent = await api.sendRoleplay(category, text.trim(), isWar ? campaignId : undefined, sabotageTarget[0]?.tg_id);
      haptic('medium');
      toast(sent.result_required === false ? 'رول امنیتی ثبت و در آرشیو ادمین ذخیره شد' : 'رول برای بررسی شورای جنگ فرستاده شد');
      setText('');
      setSabotageTarget([]);
      load();
      if (isWar) loadBattles();
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
          <select value={category} onChange={e => { setCategory(e.target.value); setSabotageTarget([]); }}>
            {Object.entries(ROLEPLAY_CATEGORIES).map(([key, name]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          {isWar && (
            <>
              <label className="f">نبرد</label>
              {battles === null ? (
                <div className="page-sub" style={{ margin: '0 4px' }}>در حال بارگذاری نبردها...</div>
              ) : battles.length === 0 ? (
                <div className="page-sub" style={{ margin: '0 4px', color: 'var(--danger)' }}>
                  فعلاً هیچ نبردِ رسیده‌ای برای نوشتن سناریو نداری — بعد از اینکه لشکری (مهاجم یا مدافع) به مقصد برسد، تا ۶ ساعت اینجا نشانش می‌دهیم
                </div>
              ) : (
                <select value={campaignId} onChange={e => setCampaignId(e.target.value)}>
                  {battles.map(b => (
                    <option key={b.campaign_id} value={b.campaign_id}>
                      {b.name} — {b.origin} ← {b.target} ({b.role === 'attacker' ? 'مهاجم' : 'مدافع'} تویی)
                    </option>
                  ))}
                </select>
              )}
            </>
          )}

          {category === 'sabotage' && (
            <>
              <label className="f">هدف خرابکاری</label>
              <PlayerPicker value={sabotageTarget} onChange={setSabotageTarget} single placeholder="نام لرد یا قلعهٔ هدف را جست‌وجو کن..." />
              <div className="page-sub" style={{ margin: '7px 4px 0' }}>این هدف همراه رول ثبت می‌شود و ادمین وضعیت منابع و محبوبیت هر دو طرف را هنگام داوری می‌بیند.</div>
            </>
          )}

          <label className="f">متن رول</label>
          <textarea value={text} onChange={e => setText(e.target.value)}
                    placeholder="سناریوت را بنویس... چه می‌کنی، چطور، و هدفت چیست؟" />

          <button className="btn" style={{ marginTop: 14 }} disabled={textTooShort || noBattleChosen || noSabotageTarget || busy} onClick={send}>
            {busy ? 'در حال ارسال...' : 'ارسال رول به شورای جنگ'}
          </button>
        </div>
      )}

      {tab === 'results' && (
        <div className="up u2">
          {rows === null && (
            <div className="loading">در حال بارگذاری...</div>
          )}
          {rows && rows.length === 0 && (
            <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>هنوز رولی نفرستاده‌ای</div>
          )}
          {rows && rows.map(r => (
            <div className="card" key={r.id} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span className="title-tag" style={{ marginInlineStart: 0 }}>{r.category_name}</span>
                <span className={`poll-status ${r.result_required === false || r.resolved ? '' : 'open'}`}>
                  {r.result_required === false ? 'ثبت شده' : r.resolved ? 'پاسخ آمد' : 'در انتظار بررسی'}
                </span>
              </div>
              <div style={{ marginTop: 10, fontSize: 12.5, lineHeight: 1.8, color: 'var(--mid)' }}>{r.text}</div>
              {r.target_player_name && <div className="page-sub" style={{ marginTop: 7 }}>هدف خرابکاری: {r.target_player_name}</div>}
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
