import { useState } from 'react';
import { NAVAL_TROOP_IDS } from '../gamedata.js';
import { arrivalText, battleExportText } from '../battleExport.js';
import { req } from '../api.js';

export default function BattleExport({ battle, toast }) {
  const [conditions, setConditions] = useState(null);
  const [deadline, setDeadline] = useState('');
  const [busy, setBusy] = useState('');
  const [preview, setPreview] = useState('summary');
  const text = battleExportText(battle, NAVAL_TROOP_IDS, conditions ?? arrivalText(battle), deadline);
  const fullText = battleExportText(battle, NAVAL_TROOP_IDS, conditions ?? arrivalText(battle), deadline, {detailed:true});
  async function copy() {
    if (busy) return;
    setBusy('copy');
    const active = document.activeElement;
    try {
      try { await navigator.clipboard.writeText(text); }
      catch {
        const field = document.createElement('textarea');
        field.value=text; field.readOnly=true; field.style.position='fixed'; field.style.opacity='0';
        document.body.appendChild(field);
        try { field.focus(); field.select(); field.setSelectionRange(0,field.value.length); if (!document.execCommand('copy')) throw new Error('copy'); }
        finally { field.remove(); active?.focus(); }
      }
      toast('اطلاعات کلی نبرد کپی شد؛ برای گزارش‌های طولانی از دانلود فایل استفاده کنید');
    } catch { toast('کپی خودکار انجام نشد؛ فایل گزارش را دانلود کنید یا متن پیش‌نمایش را کپی کنید'); }
    finally { setBusy(''); }
  }
  async function download(kind) {
    if (busy) return;
    setBusy(kind);
    try {
      const report = await req('/api/admin/battle-reports', {method:'POST',body:JSON.stringify({
        title: `گزارش ${kind==='detailed'?'کامل':'کلی'} نبرد ${battle.name || battle.location || 'نامشخص'}`.slice(0,200), text:kind==='detailed'?fullText:text,
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
        toast('دانلود گزارش نبرد آغاز شد');
      }
    } catch (error) { toast(error.status===404?'برای دانلود گزارش، نسخهٔ سرور باید به‌روز شود.':error.message || 'دانلود انجام نشد؛ دوباره تلاش کنید'); }
    finally { setBusy(''); }
  }
  return <details className="card" style={{ marginTop: 10, padding:14 }}>
    <summary style={{cursor:'pointer',color:'var(--gold)',fontWeight:800}}>دانلود و کپی اطلاعات نبرد</summary>
    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:8,marginTop:14}}>
      <button type="button" className="btn ghost" disabled={!!busy} onClick={copy}>{busy==='copy'?'در حال کپی…':'کپی اطلاعات نبرد'}</button>
      <button type="button" className="btn ghost" disabled={!!busy} onClick={()=>download('summary')}>{busy==='summary'?'در حال آماده‌سازی…':'دانلود اطلاعات کلی'}</button>
      <button type="button" className="btn" disabled={!!busy} onClick={()=>download('detailed')}>{busy==='detailed'?'در حال آماده‌سازی…':'دانلود اطلاعات کامل'}</button>
    </div>
    <p className="page-sub" style={{marginTop:10}}>کپی و گزارش کلی شامل آمار مجموع‌اند. گزارش کامل، تعداد هر نوع نیروی زمینی، کشتی و ادوات هر لشکر را هم جداگانه نشان می‌دهد. شرایط و مهلت درج‌شده در هر دو فایل حفظ می‌شوند.</p>
    <details style={{ marginTop: 8 }}>
      <summary className="page-sub" style={{ cursor: 'pointer' }}>ویرایش شرایط و مهلت · پیش‌نمایش خروجی</summary>
      <label className="f">شرایط نبرد و ترتیب ورود نیروها</label>
      <textarea aria-label="شرایط نبرد و ترتیب ورود نیروها" rows={5} value={conditions ?? arrivalText(battle)} onChange={e => setConditions(e.target.value)} />
      <label className="f">زمان ارسال سناریو</label>
      <textarea aria-label="زمان ارسال سناریو" rows={2} placeholder="مثلاً طرفین تا ساعت دو ظهر فرصت ارسال سناریو دارند." value={deadline} onChange={e => setDeadline(e.target.value)} />
      <div className="page-sub">ویرایش متن گزارش، مهلت رسمی یا شرایط نبرد را تغییر نمی‌دهد.</div>
      <label className="f">نوع پیش‌نمایش<select aria-label="نوع پیش‌نمایش گزارش" value={preview} onChange={e=>setPreview(e.target.value)}><option value="summary">اطلاعات کلی</option><option value="detailed">اطلاعات کامل و تفکیک نیروها</option></select></label>
      <label className="f">پیش‌نمایش خروجی</label>
      <textarea aria-label="پیش‌نمایش خروجی نبرد" readOnly rows={12} value={preview==='detailed'?fullText:text} style={{ width: '100%', boxSizing: 'border-box' }} />
    </details>
  </details>;
}
