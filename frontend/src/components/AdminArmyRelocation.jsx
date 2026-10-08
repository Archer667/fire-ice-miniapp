import { useState } from 'react';
import { api } from '../api.js';
import CastlePicker from './CastlePicker.jsx';

export default function AdminArmyRelocation({ army, toast, onMoved }) {
  const [open, setOpen] = useState(false);
  const [destination, setDestination] = useState([]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [battleRequired, setBattleRequired] = useState(!!army.in_battle);
  const move = async () => {
    setBusy(true);
    try {
      await api.adminRelocateCampaign(army.id, destination[0], confirm);
      toast('لشکر فوراً به مقصد منتقل شد'); setOpen(false); setDestination([]); setConfirm(false); onMoved();
    } catch (e) {
      if (e.status === 409 && e.message.includes('تأیید')) setBattleRequired(true);
      toast(e.message);
    } finally { setBusy(false); }
  };
  return <div style={{ margin: '10px 0' }}>
    <button className="btn ghost" disabled={busy} onClick={() => setOpen(!open)}>جابجایی فوری لشکر</button>
    {open && <div style={{ padding: 12, border: '1px solid var(--line)', borderRadius: 12, marginTop: 8 }}>
      <p className="page-sub">انتقال بدون زمان سفر انجام می‌شود. نیروها، آیتم‌ها و تجهیزات حفظ می‌شوند و لشکر در مقصد مستقر می‌شود.</p>
      {army.merge_group_id ? <p className="page-sub">ابتدا این عضو را از لشکر مشترک جدا کن.</p> : <>
        <label className="f">قلعهٔ مقصد</label>
        <CastlePicker value={destination} onChange={setDestination} max={1} allowOccupied />
        {battleRequired && <label className="family-confirm"><input type="checkbox" checked={confirm} disabled={busy} onChange={e => setConfirm(e.target.checked)} />خروج این لشکر از نبرد یا محاصره را تأیید می‌کنم؛ اگر طرف متخاصمی باقی نماند، پرونده بدون نتیجه بسته می‌شود.</label>}
        <button className="btn" disabled={busy || !destination.length || (battleRequired && !confirm)} onClick={move}>{busy ? 'در حال انتقال…' : 'ثبت انتقال فوری'}</button>
      </>}
    </div>}
  </div>;
}

