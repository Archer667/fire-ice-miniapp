import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic, getTgUser } from '../telegram.js';
import { Keep } from '../components/Icons.jsx';
import CastlePicker from '../components/CastlePicker.jsx';
import {REGIONS_STATIC} from '../gamedata.js';

export default function Onboarding() {
  const { setMe, toast, seasonBranding } = useGame();
  const [name, setName] = useState(getTgUser()?.first_name || '');
  const [gender, setGender] = useState('lord');
  const [mode,setMode]=useState('castle');
  const [requestedRegion,setRequestedRegion]=useState(Object.keys(REGIONS_STATIC)[0]);
  const [requestedCastles, setRequestedCastles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [registrationRegions, setRegistrationRegions] = useState([]);

  useEffect(() => {
    api.registrationOptions().then(data => setRegistrationRegions(data.regions || [])).catch(e => toast(e.message));
  }, []);

  const enter = async () => {
    if (!name.trim()) { toast('نامت را بنویس، لرد بی‌نام'); return; }
    if (!gender) { toast('عنوان کاراکتر را انتخاب کن'); return; }
    if (mode === 'castle' && requestedCastles.length === 0) { toast('دست‌کم یک قلعه را به‌عنوان اولویت انتخاب کن'); return; }
    setBusy(true);
    try {
      await api.register({ name: name.trim(), gender, registration_mode:mode, requested_region:mode === 'character' ? requestedRegion : null, requested_castles:mode === 'castle' ? requestedCastles : [] });
      const me = await api.me();
      haptic('medium');
      setMe(me);
      toast(`خوش آمدی، ${gender === 'lady' ? 'لیدی' : 'لرد'} ${name.trim()} — درخواستت برای بررسی مدیریت فرستاده شد`);
    } catch (e) { toast(e.message); }
    setBusy(false);
  };

  return (
    <div className="view view-noheader">
      <div className="hero up">
        <div className="mark"><Keep s={40} /></div>
        <h1>{seasonBranding.title}</h1>
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
      <div className="up u1" style={{marginTop:16}}><label className="f">نوع ورود به جهان والریا</label><div className="grid2" role="radiogroup" aria-label="نوع کاراکتر">{[['castle','فرمانروای قلعه'],['character','کاراکتر بدون قلعه']].map(([id,label])=><button key={id} type="button" role="radio" aria-checked={mode===id} className={`rbtn pick ${mode===id?'sel':''}`} onClick={()=>setMode(id)}><div className="n">{label}</div></button>)}</div></div>
      {mode==='castle'?<div className="up u1" style={{marginTop:12}}><label className="f">قلعه‌های درخواستی، به‌ترتیب اولویت</label><CastlePicker value={requestedCastles} onChange={setRequestedCastles} regionStates={registrationRegions}/><p className="page-sub">دست‌کم یک قلعه انتخاب کن؛ مالکیت پس از تأیید مدیریت واگذار می‌شود.</p></div>:<div className="card up u1" style={{marginTop:16}}><label className="f">اقلیم درخواستی<select value={requestedRegion} onChange={e=>setRequestedRegion(e.target.value)}>{Object.entries(REGIONS_STATIC).map(([id,r])=><option key={id} value={id}>{r.name}</option>)}</select></label><p className="page-sub">با تأیید مدیریت و تعیین محل اقامت، سفر، خانواده، نهادها و امور شخصی در دسترس قرار می‌گیرند. اقامت در یک قلعه به معنای مالکیت آن نیست.</p></div>}
      <div className="page-sub up u2" style={{ margin: '4px 4px 0' }}>
        نوع عضویت، اقلیم و محل اقامت یا قلعه پس از بررسی درخواست مشخص می‌شوند.
      </div>
      <div className="up u2" style={{ marginTop: 16 }}>
        <button className="btn" onClick={enter} disabled={busy}>
          {busy ? 'در حال ثبت‌نام...' : 'ثبت‌نام'}
        </button>
      </div>
    </div>
  );
}
