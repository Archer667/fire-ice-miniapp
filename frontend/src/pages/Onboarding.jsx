import { useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic, getTgUser } from '../telegram.js';
import { Keep } from '../components/Icons.jsx';

export default function Onboarding() {
  const { setMe, toast } = useGame();
  const [name, setName] = useState(getTgUser()?.first_name || '');
  const [gender, setGender] = useState('lord');
  const [busy, setBusy] = useState(false);

  const enter = async () => {
    if (!name.trim()) { toast('نامت را بنویس، لرد بی‌نام'); return; }
    setBusy(true);
    try {
      await api.register({ name: name.trim(), gender });
      const me = await api.me();
      haptic('medium');
      setMe(me);
      toast(`خوش آمدی، ${gender === 'lady' ? 'لیدی' : 'لرد'} ${name.trim()} — منتظر بمان تا ادمین خاندانت را مشخص کند`);
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <div className="view view-noheader">
      <div className="hero up">
        <div className="mark"><Keep s={40} /></div>
        <h1>نغمه آتش و یخ</h1>
        <p>وقتی بازیِ تاج‌وتخت می‌کنی، یا می‌بری یا می‌میری</p>
      </div>
      <div className="up u1">
        <label className="f">نام کاراکتر</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="جان اسنو" />
      </div>
      <div className="up u1">
        <label className="f">عنوان</label>
        <div className="grid2" role="radiogroup" aria-label="عنوان">
          <button type="button" role="radio" aria-checked={gender === 'lord'}
                  className={`rbtn pick ${gender === 'lord' ? 'sel' : ''}`} onClick={() => { haptic(); setGender('lord'); }}>
            <div className="n">لرد</div>
          </button>
          <button type="button" role="radio" aria-checked={gender === 'lady'}
                  className={`rbtn pick ${gender === 'lady' ? 'sel' : ''}`} onClick={() => { haptic(); setGender('lady'); }}>
            <div className="n">لیدی</div>
          </button>
        </div>
      </div>
      <div className="page-sub up u2" style={{ margin: '4px 4px 0' }}>
        اقلیم و قلعه‌ات را انتخاب نمی‌کنی — بعد از ثبت‌نام، ادمین بازی خاندان و قلعه‌ات را برایت مشخص می‌کند
      </div>
      <div className="up u2" style={{ marginTop: 16 }}>
        <button className="btn" onClick={enter} disabled={busy}>
          {busy ? 'در حال ثبت‌نام...' : 'ثبت‌نام'}
        </button>
      </div>
    </div>
  );
}
