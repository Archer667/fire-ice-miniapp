import { useState } from 'react';
import { NAVAL_TROOP_IDS } from '../gamedata.js';
import { arrivalText, battleExportText } from '../battleExport.js';

export default function BattleExport({ battle, toast }) {
  const [conditions, setConditions] = useState(null);
  const [deadline, setDeadline] = useState('');
  const text = battleExportText(battle, NAVAL_TROOP_IDS, conditions ?? arrivalText(battle), deadline);
  async function copy() {
    try {
      try { await navigator.clipboard.writeText(text); }
      catch {
        const field = document.createElement('textarea');
        field.value = text; field.style.position = 'fixed'; field.style.opacity = '0';
        document.body.appendChild(field);
        try { field.focus(); field.select(); if (!document.execCommand('copy')) throw new Error('copy'); }
        finally { field.remove(); }
      }
      toast('اطلاعات نبرد کپی شد');
    } catch { toast('کپی خودکار انجام نشد؛ متن پیش‌نمایش را انتخاب و کپی کن'); }
  }
  return <div style={{ marginTop: 10 }}>
    <button type="button" className="btn ghost" onClick={copy}>کپی اطلاعات نبرد</button>
    <details style={{ marginTop: 8 }}>
      <summary className="page-sub" style={{ cursor: 'pointer' }}>ویرایش شرایط و مهلت · پیش‌نمایش خروجی</summary>
      <label className="f">شرایط نبرد و ترتیب ورود نیروها</label>
      <textarea aria-label="شرایط نبرد و ترتیب ورود نیروها" rows={5} value={conditions ?? arrivalText(battle)} onChange={e => setConditions(e.target.value)} />
      <label className="f">زمان ارسال سناریو</label>
      <textarea aria-label="زمان ارسال سناریو" rows={2} placeholder="مثلاً طرفین تا ساعت دو ظهر فرصت ارسال سناریو دارند." value={deadline} onChange={e => setDeadline(e.target.value)} />
      <div className="page-sub">این متن‌ها برای خروجی همین صفحه‌اند؛ مهلت یا قوانین نبرد را تغییر نمی‌دهند.</div>
      <label className="f">پیش‌نمایش خروجی</label>
      <textarea aria-label="پیش‌نمایش خروجی نبرد" readOnly rows={12} value={text} style={{ width: '100%', boxSizing: 'border-box' }} />
    </details>
  </div>;
}
