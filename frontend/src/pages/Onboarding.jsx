import { useState } from 'react';
import { useGame } from '../store.jsx';
import { api } from '../api.js';
import { haptic, getTgUser } from '../telegram.js';
import { Keep } from '../components/Icons.jsx';
import CastlePicker from '../components/CastlePicker.jsx';

function optimizeProfileImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('خواندن عکس ممکن نشد'));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error('فرمت عکس قابل‌خواندن نیست'));
      image.onload = () => {
        const maxSide = 512;
        const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
        const width = Math.max(1, Math.round(image.naturalWidth * scale));
        const height = Math.max(1, Math.round(image.naturalHeight * scale));
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(image, 0, 0, width, height);
        resolve(canvas.toDataURL('image/webp', 0.78));
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

export default function Onboarding() {
  const { setMe, toast } = useGame();
  const [name, setName] = useState(getTgUser()?.first_name || '');
  const [gender, setGender] = useState('lord');
  const [requestedCastles, setRequestedCastles] = useState([]);
  const [backstory, setBackstory] = useState('');
  const [profileImage, setProfileImage] = useState(null);
  const [busy, setBusy] = useState(false);

  const enter = async () => {
    if (!name.trim()) { toast('نامت را بنویس، لرد بی‌نام'); return; }
    if (backstory.trim().length < 40) { toast('بک‌استوری کاراکترت باید حداقل ۴۰ نویسه باشد'); return; }
    setBusy(true);
    try {
      await api.register({ name: name.trim(), gender, requested_castles: requestedCastles, backstory: backstory.trim(), profile_image: profileImage });
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
      <div className="up u1" style={{ marginTop: 12 }}>
        <label className="f">عکس پروفایل کاراکتر (اختیاری، حداکثر ۲٫۵ مگابایت)</label>
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={async e => {
          const file = e.target.files?.[0];
          if (!file) { setProfileImage(null); return; }
          if (file.size > 2.5 * 1024 * 1024) { toast('حجم عکس بیشتر از ۲٫۵ مگابایت است'); e.target.value = ''; return; }
          try {
            setProfileImage(await optimizeProfileImage(file));
          } catch (error) {
            toast(error.message);
            e.target.value = '';
          }
        }} />
        {profileImage && <img src={profileImage} alt="پیش‌نمایش عکس کاراکتر" style={{ width: 86, height: 86, borderRadius: '50%', objectFit: 'cover', marginTop: 9, border: '2px solid var(--az2)' }} />}
      </div>
      <div className="up u1" style={{ marginTop: 12 }}>
        <label className="f">بک‌استوری کاراکتر</label>
        <textarea value={backstory} onChange={e => setBackstory(e.target.value)} minLength={40} maxLength={2000} placeholder="گذشته، انگیزه‌ها، خلق‌وخو و هدف کاراکترت را بنویس..." />
        <div className="page-sub" style={{ marginTop: 5 }}>{backstory.length.toLocaleString('fa-IR')} از ۲۰۰۰ نویسه</div>
      </div>
      <div className="up u1" style={{ marginTop: 12 }}>
        <label className="f">خاندان‌های درخواستی (اختیاری، به‌ترتیب اولویت)</label>
        <CastlePicker value={requestedCastles} onChange={setRequestedCastles} />
        <div className="page-sub" style={{ margin: '6px 4px 0' }}>
          چون ممکنه اولی‌ها قبلاً اشغال شده باشن، چندتا اسم به‌ترتیبِ علاقه‌ات بده — ادمین با
          توجه به همین لیست خاندان و قلعه‌ات را نهایی می‌کند
        </div>
      </div>
      <div className="page-sub up u2" style={{ margin: '4px 4px 0' }}>
        اقلیم و قلعه‌ات را خودت نهایی نمی‌کنی — بعد از ثبت‌نام، ادمین بازی با توجه به درخواستت خاندان و قلعه‌ات را برایت مشخص می‌کند
      </div>
      <div className="up u2" style={{ marginTop: 16 }}>
        <button className="btn" onClick={enter} disabled={busy}>
          {busy ? 'در حال ثبت‌نام...' : 'ثبت‌نام'}
        </button>
      </div>
    </div>
  );
}
