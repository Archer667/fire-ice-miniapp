import { useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { REGIONS_STATIC } from '../gamedata.js';
import { haptic, getTgUser } from '../telegram.js';
import { Keep } from '../components/Icons.jsx';

export default function Onboarding() {
  const { setMe, toast } = useGame();
  const [step, setStep] = useState(1);
  const [name, setName] = useState(getTgUser()?.first_name || '');
  const [regionId, setRegionId] = useState('north');
  const [castle, setCastle] = useState(null);
  const [busy, setBusy] = useState(false);

  const region = REGIONS_STATIC[regionId];

  const next = () => {
    if (!name.trim()) { toast('نامت را بنویس، لرد بی‌نام'); return; }
    haptic(); setCastle(null); setStep(2);
  };

  const enter = async () => {
    if (!castle) { toast('قلعه‌ات را انتخاب کن'); return; }
    setBusy(true);
    try {
      await api.register({ name: name.trim(), region: regionId, castle });
      const me = await api.me();
      haptic('medium');
      setMe(me);
      toast(`خوش آمدی به وستروس، لرد ${name.trim()}`);
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  if (step === 1) return (
    <div className="view">
      <div className="hero up">
        <div className="mark"><Keep s={40} /></div>
        <h1>نغمه آتش و یخ</h1>
        <p>وقتی بازیِ تاج‌وتخت می‌کنی، یا می‌بری یا می‌میری</p>
        <div className="steps"><i className="on" /><i /></div>
      </div>
      <div className="up u1">
        <label className="f">نام کاراکتر</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="جان اسنو" />
      </div>
      <div className="up u2">
        <label className="f">اقلیم خود را برگزین</label>
        <div className="grid3">
          {Object.entries(REGIONS_STATIC).map(([id, r]) => (
            <div key={id} className={`pick ${regionId === id ? 'sel' : ''}`}
                 onClick={() => { haptic(); setRegionId(id); }}>
              <div className="g">{r.g}</div>
              <div className="n">{r.name}</div>
              <div className="c">{r.castles.length + r.ports.length} قلعه و بندر</div>
            </div>
          ))}
        </div>
      </div>
      <div className="up u3" style={{ marginTop: 20 }}>
        <button className="btn" onClick={next}>ادامه — انتخاب قلعه</button>
      </div>
    </div>
  );

  return (
    <div className="view">
      <div className="hero up" style={{ paddingBottom: 16 }}>
        <h1 style={{ fontSize: 21 }}>قلعه‌ای در {region.name}</h1>
        <p>{region.castles.length} قلعه و {region.ports.length} بندر · بندر = ناوگان</p>
        <div className="steps"><i className="on" /><i className="on" /></div>
      </div>
      <div className="castles up u1">
        {[...region.castles.map(n => ({ n, port: false })),
          ...region.ports.map(n => ({ n, port: true }))].map(c => (
          <div key={c.n} className={`castle ${castle === c.n ? 'sel' : ''}`}
               onClick={() => { haptic(); setCastle(c.n); }}>
            {c.n}
            {c.port && <span className="tag">بندر — ناوگان</span>}
          </div>
        ))}
      </div>
      <div className="up u2" style={{ marginTop: 18 }}>
        <button className="btn" onClick={enter} disabled={busy}>
          {busy ? 'در حال ثبت...' : 'ورود به وستروس'}
        </button>
        <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => setStep(1)}>بازگشت</button>
      </div>
    </div>
  );
}
