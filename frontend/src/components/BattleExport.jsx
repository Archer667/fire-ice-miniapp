import { useState } from 'react';
import { NAVAL_TROOP_IDS } from '../gamedata.js';
import { arrivalText, battleExportText } from '../battleExport.js';
import { req } from '../api.js';

export default function BattleExport({ battle, toast }) {
  const [conditions, setConditions] = useState(null);
  const [deadline, setDeadline] = useState('');
  const [busy, setBusy] = useState(false);
  const text = battleExportText(battle, NAVAL_TROOP_IDS, conditions ?? arrivalText(battle), deadline);
  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      const report = await req('/api/admin/battle-reports', {method:'POST',body:JSON.stringify({
        title: `گزارش نبرد ${battle.name || battle.location || 'نامشخص'}`.slice(0,200), text,
      })});
      const url = new URL(report.path, location.origin).href;
      const tg = window.Telegram?.WebApp;
      if (tg?.downloadFile && tg.isVersionAtLeast?.('8.0')) {
        tg.downloadFile({url, file_name:report.filename}, accepted => {
          toast(accepted ? 'دانلود گزارش درخواست شد' : 'دانلود انجام نشد؛ برای تلاش دوباره دکمهٔ دانلود را بزنید');
        });
      } else {
        const link = document.createElement('a');
        link.href = url; link.download = report.filename;
        document.body.appendChild(link); link.click(); link.remove();
        toast('دانلود گزارش کامل نبرد آغاز شد');
      }
    } catch (error) { toast(error.status===404?'برای دانلود گزارش، نسخهٔ سرور باید به‌روز شود.':error.message || 'دانلود انجام نشد؛ دوباره تلاش کنید'); }
    finally { setBusy(false); }
  }
  return <div style={{ marginTop: 10 }}>
    <button type="button" className="btn ghost" disabled={busy} onClick={download}>{busy?'در حال آماده‌سازی فایل…':'دانلود گزارش کامل نبرد'}</button>
    <div className="page-sub" style={{marginTop:6}}>فایل فارسی و قابل چاپ؛ شامل متن کامل گزارش، شرایط و مهلت درج‌شده در پیش‌نمایش.</div>
    <details style={{ marginTop: 8 }}>
      <summary className="page-sub" style={{ cursor: 'pointer' }}>ویرایش شرایط و مهلت · پیش‌نمایش خروجی</summary>
      <label className="f">شرایط نبرد و ترتیب ورود نیروها</label>
      <textarea aria-label="شرایط نبرد و ترتیب ورود نیروها" rows={5} value={conditions ?? arrivalText(battle)} onChange={e => setConditions(e.target.value)} />
      <label className="f">زمان ارسال سناریو</label>
      <textarea aria-label="زمان ارسال سناریو" rows={2} placeholder="مثلاً طرفین تا ساعت دو ظهر فرصت ارسال سناریو دارند." value={deadline} onChange={e => setDeadline(e.target.value)} />
      <div className="page-sub">ویرایش متن گزارش، مهلت رسمی یا شرایط نبرد را تغییر نمی‌دهد.</div>
      <label className="f">پیش‌نمایش خروجی</label>
      <textarea aria-label="پیش‌نمایش خروجی نبرد" readOnly rows={12} value={text} style={{ width: '100%', boxSizing: 'border-box' }} />
    </details>
  </div>;
}
