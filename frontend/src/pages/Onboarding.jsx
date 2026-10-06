import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic, getTgUser } from '../telegram.js';
import { Keep } from '../components/Icons.jsx';
import CastlePicker from '../components/CastlePicker.jsx';

export default function Onboarding() {
  const { setMe, toast } = useGame();
  const [name, setName] = useState(getTgUser()?.first_name || '');
  const [gender, setGender] = useState('lord');
  const [requestedCastles, setRequestedCastles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [registrationRegions, setRegistrationRegions] = useState([]);

  useEffect(() => {
    api.registrationOptions().then(data => setRegistrationRegions(data.regions || [])).catch(e => toast(e.message));
  }, []);

  const enter = async () => {
    if (!name.trim()) { toast('نامت را بنویس، لرد بی‌نام'); return; }
    if (!gender) { toast('عنوان کاراکتر را انتخاب کن'); return; }
    if (requestedCastles.length === 0) { toast('دست‌کم یک قلعه را به‌عنوان اولویت انتخاب کن'); return; }
    setBusy(true);
    try {
      await api.register({ name: name.trim(), gender, requested_castles: requestedCastles });
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
        <h1>والریا : سیزن اول</h1>
        <p>هر تصمیم، یک پیامد . هر انتخاب، یک سرنوشت .</p>
      </div>
      <div className="up u1">
        <label className="f">نام کاراکتر</label>
        <input required value={name} onChange={e => setName(e.target.value)} placeholder="جان اسنو" />
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
      <div className="up u1" style={{ marginTop: 12 }}>
        <label className="f">قلعه‌های درخواستی (اجباری، به‌ترتیب اولویت)</label>
        <CastlePicker value={requestedCastles} onChange={setRequestedCastles} regionStates={registrationRegions} />
        <div className="page-sub" style={{ margin: '6px 4px 0' }}>
          قلعه‌های دلخواهت را به‌ترتیب اولویت انتخاب کن. چند انتخاب از اقلیم‌های مختلف، امکان واگذاری قلعه را بیشتر می‌کند.
        </div>
      </div>
      <div className="page-sub up u2" style={{ margin: '4px 4px 0' }}>
        برای تأیید درخواست، باید در تنظیمات حساب تلگرام خود نام کاربری (Username / @ID) تعیین کرده باشی. بعد از تنظیم، بازی را دوباره باز کن.
        <br />
        اقلیم و قلعهٔ خاندان پس از بررسی درخواست عضویت، با توجه به اولویت‌هایت تعیین می‌شوند.
      </div>
      <div className="up u2" style={{ marginTop: 16 }}>
        <button className="btn" onClick={enter} disabled={busy}>
          {busy ? 'در حال ثبت‌نام...' : 'ثبت‌نام'}
        </button>
      </div>
    </div>
  );
}
