import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { seasonTitle } from '../seasonBranding.js';

export default function AdminSeasonBranding() {
  const { setSeasonBranding, toast } = useGame();
  const [data, setData] = useState(null);
  const [number, setNumber] = useState('1');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true); setError('');
    try {
      const value = await api.seasonBranding();
      setData(value); setNumber(String(value.number)); setName(value.name);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  const valid = /^\d+$/.test(number) && Number(number) >= 1 && Number(number) <= 9999;
  const changed = data && (Number(number) !== data.number || name.trim() !== data.name);
  const save = async event => {
    event.preventDefault();
    if (!valid || !changed || busy) return;
    setBusy(true); setError('');
    try {
      const value = await api.adminSaveSeasonBranding({ number: Number(number), name: name.trim(), revision: data.revision });
      setData(value); setNumber(String(value.number)); setName(value.name); setSeasonBranding(value);
      toast('شماره و نام سیزن ذخیره شد');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <section className="card up">
    <h3>شماره و نام سیزن</h3>
    <p className="page-sub">عنوان سیزن جاری در ثبت‌نام، لیدربرد و پیام خوشامد بات نمایش داده می‌شود. نام سیزن اختیاری است.</p>
    {error && <p role="alert">{error}</p>}
    {loading ? <p className="loading">در حال دریافت تنظیمات…</p> : !data ? <button className="btn ghost" onClick={load}>تلاش دوباره</button> :
      <form onSubmit={save}>
        <label className="f" htmlFor="season-number">شماره سیزن</label>
        <div style={{display:'flex',gap:8,alignItems:'center'}}>
          <button type="button" className="btn ghost" aria-label="کاهش شماره سیزن" disabled={busy || !valid || Number(number)<=1} onClick={()=>setNumber(String(Number(number)-1))} style={{width:48,flexShrink:0}}>−</button>
          <input id="season-number" type="number" inputMode="numeric" min="1" max="9999" step="1" required disabled={busy} value={number} onChange={e=>setNumber(e.target.value)} style={{minWidth:0,textAlign:'center'}}/>
          <button type="button" className="btn ghost" aria-label="افزایش شماره سیزن" disabled={busy || !valid || Number(number)>=9999} onClick={()=>setNumber(String(Number(number)+1))} style={{width:48,flexShrink:0}}>+</button>
        </div>
        <label className="f" htmlFor="season-name">نام سیزن <span className="page-sub">(اختیاری)</span></label>
        <input id="season-name" maxLength={80} value={name} disabled={busy} onChange={e=>setName(e.target.value)} placeholder="مثلاً عصر اژدها"/>
        <div className="control-sub" style={{marginTop:16,overflowWrap:'anywhere'}}>
          <p className="page-sub">پیش‌نمایش عنوان</p>
          <strong style={{color:'var(--gold)'}}>{valid ? seasonTitle(Number(number),name) : 'شماره‌ای بین ۱ تا ۹۹۹۹ وارد کنید'}</strong>
        </div>
        <p className="page-sub">این تنظیم فقط عنوان سیزن را تغییر می‌دهد. زمان بازی، تقویم فصل‌ها، امتیازها و دارایی بازیکنان تغییر نمی‌کنند.</p>
        <div className="grid2">
          <button className="btn" disabled={busy || !valid || !changed}>{busy?'در حال ذخیره…':'ذخیره عنوان سیزن'}</button>
          <button className="btn ghost" type="button" disabled={busy} onClick={load}>دریافت آخرین تنظیمات</button>
        </div>
      </form>}
  </section>;
}
