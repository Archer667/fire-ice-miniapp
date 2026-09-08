import { createPortal } from 'react-dom';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';

export default function RetireCharacterDialog({ player, action, onClose, onDone }) {
  const ref = useRef(null);
  const { toast } = useGame();
  const [succession, setSuccession] = useState(null);
  const [killHeirs, setKillHeirs] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [reason, setReason] = useState('');
  const [narrative, setNarrative] = useState('');
  const [blacklisted, setBlacklisted] = useState(false);
  const [loading, setLoading] = useState(action === 'death');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const previousFocus = document.activeElement;
    const root = document.getElementById('root');
    const previousInert = root?.inert;
    if (root) root.inert = true;
    ref.current?.querySelector('textarea')?.focus();
    let active = true;
    if (action === 'death') Promise.all([api.adminGetPlayerProfile(player.tg_id), api.successionPreview(player.tg_id)]).then(([p,s]) => { if (active) { setNarrative(p.backstory || ''); setSuccession(s); } })
      .catch(e => { if (active) { setFailed(true); toast(e.message); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; if (root) root.inert = previousInert; previousFocus?.focus?.(); };
  }, []);
  const hasHeir = action === 'death' && succession?.heir && !killHeirs;
  const consequence = hasHeir ? `جانشین: ${succession.heir.name}. قلعه‌ها، لشکرها، پروژه‌ها، منابع، امتیازها و مدال‌ها حفظ می‌شوند؛ فقط کاراکتر می‌میرد.` : action === 'death' && !killHeirs && succession?.has_minors ? 'به‌دلیل به بلوغ نرسیدن وراث، جانشینی انجام نمی‌شود؛ قلعه‌ها آزاد و فعالیت‌های کاراکتر لغو می‌شوند.' : action === 'death' && !killHeirs ? 'به‌دلیل نداشتن وارث بالغ، قلعه‌ها آزاد و فعالیت‌ها لغو می‌شوند.' : 'همهٔ قلعه‌های فعلی آزاد می‌شوند و سطح ساختمان‌ها حفظ می‌شود. منابع به مقدار شروع بازی برمی‌گردند؛ لشکرها و فعالیت‌ها لغو می‌شوند.';
  return createPortal(<div className="character-overlay"><div ref={ref} className="character-dialog" role="dialog" aria-modal="true" aria-labelledby="retire-character-title" onKeyDown={e => {
    if (e.key === 'Escape') { e.preventDefault(); if (!busy) onClose(); }
    if (e.key === 'Tab') {
      const fields = [...ref.current.querySelectorAll('button:not(:disabled), textarea:not(:disabled), input:not(:disabled), summary')].filter(el => el.getClientRects().length);
      const first = fields[0], last = fields[fields.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    }
  }}>
    <h2 id="retire-character-title" className="sect">{action === 'death' ? 'مرگ کاراکتر' : 'حذف بازیکن'} — {player.name}</h2>
    <p className="page-sub">شناسهٔ تلگرام: {player.tg_id}</p>
    <p>{loading ? 'در حال بررسی وارثان…' : consequence}</p>
    <form onSubmit={async e => {
      e.preventDefault(); setBusy(true);
      try { await api.retireCharacter(player.tg_id, { action, reason, narrative, blacklisted, kill_heirs: killHeirs, character_key: succession?.character_key || player.character_key }); toast(action === 'death' ? 'مرگ ثبت شد؛ اعلان همگانی در صف ارسال است' : 'بازیکن حذف شد'); onDone(); }
      catch (err) { toast(err.message); setBusy(false); }
    }}>
      {action === 'death' && succession && <div className="family-death-choices"><label><input type="radio" name="death-mode" disabled={busy} checked={!killHeirs} onChange={()=>{setKillHeirs(false);setConfirmed(false);}}/>فقط مرگ کاراکتر؛ جانشینی در صورت داشتن وارث بالغ</label><label><input type="radio" name="death-mode" disabled={busy} checked={killHeirs} onChange={()=>{setKillHeirs(true);setConfirmed(false);}}/>مرگ کاراکتر همراه تمام وارثان وابسته</label><p>وارثان این خاندان: {succession.children.map(c=>c.name).join('، ') || 'ندارد'}</p>{killHeirs && <label className="family-danger"><input type="checkbox" disabled={busy} required checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>مرگ همهٔ وارثان بالا و لغو فعالیت‌ها را تأیید می‌کنم. فرزندان ساکن خاندان طرف دیگر شامل نمی‌شوند.</label>}</div>}
      <label className="f">{action === 'death' ? 'علت مرگ (در اعلان نمایش داده می‌شود)' : 'دلیل حذف'}<textarea disabled={busy} required={action === 'death'} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
      {action === 'death' && <><label className="f">روایت کاراکتر — قابل ویرایش یا حذف<textarea rows={7} disabled={loading || busy} maxLength={2000} value={narrative} onChange={e => setNarrative(e.target.value)} /></label><p className="page-sub">{loading ? 'در حال دریافت بک‌استوری…' : 'این ویرایش فقط برای اعلان مرگ است. متن خالی در اعلان نمایش داده نمی‌شود.'}</p>
        <details><summary>پیش‌نمایش متن اعلان</summary><p style={{whiteSpace:'pre-wrap'}}>🐦‍⬛ کلاغ سیاه از راه رسید{'\n\n'}⚔️ {player.gender === 'lady' ? 'لیدی' : 'لرد'} {player.name} درگذشت{player.house ? '\nاز خاندان '+player.house : ''}{player.castle ? '\nفرمانروای قلعهٔ '+player.castle : ''}{'\n\n'}📜 علت مرگ به اعلام مدیریت:{'\n'}{reason}{'\n\n'}{hasHeir ? `♛ ${succession.heir.name} جانشین شد؛ دارایی‌ها و فعالیت‌ها حفظ شدند.` : '🏰 قلعه‌های این کاراکتر آزاد شدند؛ سطح ساختمان‌ها حفظ می‌شود.'}{narrative.trim() ? '\n\n📖 روایت کاراکتر\n'+narrative.trim() : ''}{'\n\n'}🕯 داستان این کاراکتر به پایان رسید.</p></details></>}
      <label className="character-blacklist"><input type="checkbox" disabled={busy} checked={blacklisted} onChange={e => setBlacklisted(e.target.checked)} />افزودن آیدی عددی به لیست سیاه دائمی</label>
      <p className="page-sub">این علامت با ریست فصل یا ریست کلی پاک نمی‌شود. انتخاب نکردن آن، سابقهٔ لیست سیاه قبلی را حذف نمی‌کند.</p>
      <div className="grid2"><button type="button" className="btn ghost" disabled={busy} onClick={onClose}>انصراف</button><button className="btn" disabled={busy || loading || failed || (killHeirs && !confirmed)}>{busy ? 'در حال ثبت…' : action === 'death' ? 'ثبت مرگ و ارسال اعلان' : 'تأیید حذف بازیکن'}</button></div>
    </form>
  </div></div>, document.body);
}
