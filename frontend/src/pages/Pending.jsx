import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { Keep } from '../components/Icons.jsx';

export default function Pending({ goTo }) {
  const { me, setMe, toast } = useGame();
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const t = setInterval(() => {
      api.me().then(m => { if (!m.pending) setMe(m); }).catch(() => {});
    }, 15000);
    return () => clearInterval(t);
  }, []);

  const checkNow = async () => {
    setChecking(true);
    try {
      const m = await api.me();
      if (m.pending) toast('هنوز ادمین خاندانت را مشخص نکرده — کمی صبر کن');
      else setMe(m);
    } catch (e) { toast(e.message); }
    setChecking(false);
  };

  return (
    <div className="view view-noheader">
      <div className="hero up">
        <div className="mark"><Keep s={40} /></div>
        <h1>{me.gender === 'lady' ? 'لیدی' : 'لرد'} {me.name}</h1>
        <p>ثبت‌نامت انجام شد — منتظر بمان تا ادمین بازی خاندان (اقلیم) و قلعه‌ات را برایت مشخص کند</p>
      </div>
      <div className="up u1">
        <button className="btn ghost" disabled={checking} onClick={checkNow}>
          {checking ? 'در حال بررسی...' : 'بررسی دوباره'}
        </button>
      </div>
      {me.admin_role && (
        <div className="up u2" style={{ marginTop: 10 }}>
          <button className="btn" onClick={() => goTo(6)}>پنل ادمین — تخصیص خاندان به بازیکن‌ها</button>
        </div>
      )}
    </div>
  );
}
