import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { api } from '../api.js';
import { Coin, Wheat, People, Pick, Rock, Wood, Wine, Build, Swords, Eye, Heart, Popularity, Blossom, SunIcon, Leaf, Snowflake, Gift } from '../components/Icons.jsx';
import { SEASONS, seasonOf } from '../seasons.js';
import { WEAPON_NAMES, castleLabel } from '../gamedata.js';
import ProfileImageModal from '../components/ProfileImageModal.jsx';

const SEASON_ICON = { spring: Blossom, summer: SunIcon, autumn: Leaf, winter: Snowflake };

const RES_META = {
  gold:  { name: 'طلا', d: 'تولید: معدن و بازار · سقف: خزانه', Icon: Coin,  max: 2000 },
  food:  { name: 'غذا', d: 'تولید: مزرعه و دامداری · سقف: انبار غذا', Icon: Wheat, max: 2000 },
  men:   { name: 'نیروی انسانی', d: 'رشد با محبوبیت · سقف با دهکده', Icon: People, max: 1000 },
  wood:  { name: 'چوب', d: 'تولید: چوب‌بری · سقف: انبار کالا', Icon: Wood, max: 800 },
  iron:  { name: 'آهن', d: 'تولید: معدن آهن · سقف: انبار کالا', Icon: Pick, max: 500 },
  stone: { name: 'سنگ', d: 'تولید: معدن سنگ · سقف: انبار کالا', Icon: Rock, max: 500 },
  wine:  { name: 'شراب', d: 'تولید: می‌کده · سقف کمتر در انبار کالا', Icon: Wine, max: 300 },
};

const WEAPON_META = {
  weapon_sword:  { d: 'تولید: کارگاه · سقف: انبار تسلیحات', max: 300 },
  weapon_spear:  { d: 'تولید: کارگاه · سقف: انبار تسلیحات', max: 300 },
  weapon_archer: { d: 'تولید: کارگاه · سقف: انبار تسلیحات', max: 300 },
  weapon_lcav:   { d: 'تولید: کارگاه · سقف: انبار تسلیحات', max: 200 },
  weapon_hcav:   { d: 'تولید: کارگاه · سقف: انبار تسلیحات', max: 200 },
};

const RANK_LABEL_FA = { overlord: 'بالادستی اقلیم', warden: 'والی', king: 'پادشاه/ملکه' };

export default function Dashboard({ goTo }) {
  const { me, setMe, toast } = useGame();
  const dayPct = Math.round((me.day / me.season_length) * 100);
  const C = 2 * Math.PI * 19;
  const [taxBusy, setTaxBusy] = useState(false);
  const [profileImageOpen, setProfileImageOpen] = useState(false);
  const season = seasonOf(me.day);
  const { name: seasonName, from: seasonFrom, to: seasonTo } = SEASONS[season];
  const SeasonIcon = SEASON_ICON[season];

  const [daily, setDaily] = useState(null);
  const [dailyBusy, setDailyBusy] = useState(false);
  const [rebellion, setRebellion] = useState(null);
  const [rationBusy, setRationBusy] = useState(false);
  const [rebellionText, setRebellionText] = useState('');
  const [rebellionBusy, setRebellionBusy] = useState(false);
  useEffect(() => {
    api.dailyStatus().then(setDaily).catch(() => {});
    api.rebellionStatus().then(setRebellion).catch(() => {});
  }, []);

  const claimDaily = async () => {
    setDailyBusy(true);
    try {
      const res = await api.dailyClaim();
      haptic('medium');
      setMe({ ...me, resources: res.resources });
      setDaily(prev => ({ ...prev, claimed_today: true, current_streak: res.streak }));
      toast(`روز ${res.day_in_cycle.toLocaleString('fa-IR')} از ۷ — جایزه گرفته شد`);
    } catch (e) { toast(e.message); }
    setDailyBusy(false);
  };

  const changeRation = async (level) => {
    setRationBusy(true);
    try {
      await api.setFoodRation(level);
      haptic();
      const fresh = await api.rebellionStatus();
      setRebellion(fresh);
      toast('سهم غله مردم ثبت شد؛ اثرش در محاسبه روزانه اعمال می‌شود');
    } catch (e) { toast(e.message); }
    setRationBusy(false);
  };

  const submitRebellion = async () => {
    if (rebellionText.trim().length < 10) { toast('رول شورش خیلی کوتاه است'); return; }
    setRebellionBusy(true);
    try {
      await api.submitRebellionRoleplay(rebellion.active.id, rebellionText.trim());
      haptic('medium');
      setRebellion(prev => ({ ...prev, active: { ...prev.active, status: 'roleplay_submitted', roleplay_text: rebellionText.trim() } }));
      toast('رول مقابله با شورش برای ادمین‌ها فرستاده شد');
    } catch (e) { toast(e.message); }
    setRebellionBusy(false);
  };

  const changeTax = async (delta) => {
    const rate = Math.max(0, Math.min(100, me.tax_rate + delta));
    if (rate === me.tax_rate) return;
    setTaxBusy(true);
    try {
      await api.setTax(rate);
      haptic();
      setMe({ ...me, tax_rate: rate });
      const fresh = await api.rebellionStatus();
      setRebellion(fresh);
    } catch (e) { toast(e.message); }
    setTaxBusy(false);
  };

  return (
    <>
      {daily && (
        <div className={`daily-card up ${daily.claimed_today ? 'done' : ''}`}>
          <div className="daily-ic"><Gift s={22} /></div>
          <div className="daily-mid">
            <div className="daily-t1">
              {daily.claimed_today ? 'جایزهٔ امروز رو گرفتی' : `جایزهٔ روز ${daily.day_in_cycle.toLocaleString('fa-IR')} از ۷`}
            </div>
            <div className="daily-t2">
              {daily.claimed_today
                ? `${daily.current_streak.toLocaleString('fa-IR')} روز پیاپی سر زدی — فردا دوباره بیا`
                : Object.entries(daily.reward).map(([k, v]) => `${v.toLocaleString('fa-IR')} ${RES_META[k]?.name || k}`).join(' · ')}
            </div>
          </div>
          {!daily.claimed_today && (
            <button type="button" className="rbtn daily-btn" disabled={dailyBusy} onClick={claimDaily}>
              {dailyBusy ? '...' : 'دریافت'}
            </button>
          )}
        </div>
      )}
      {daily && (
        <div className="streak-flames up">
          {Array.from({ length: daily.cycle_length }, (_, i) => i + 1).map(day => {
            const lit = daily.claimed_today ? day <= daily.day_in_cycle : day < daily.day_in_cycle;
            const isNext = !daily.claimed_today && day === daily.day_in_cycle;
            return (
              <div key={day} className={`streak-flame ${lit ? 'lit' : ''} ${isNext ? 'next' : ''}`}>
                <span className="fl">🔥</span>
                <span className="fd">{day.toLocaleString('fa-IR')}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className={`season up ${season}`}>
        <SeasonIcon s={92} className="season-deco" />
        <div className="ring">
          <svg width="46" height="46" viewBox="0 0 46 46">
            <circle cx="23" cy="23" r="19" fill="none" stroke="rgba(160,195,255,0.12)" strokeWidth="4" />
            <circle cx="23" cy="23" r="19" fill="none" stroke="url(#gr)" strokeWidth="4"
                    strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - dayPct / 100)} />
            <defs><linearGradient id="gr" x1="0" y1="0" x2="1" y2="1">
              <stop stopColor={seasonFrom} /><stop offset="1" stopColor={seasonTo} />
            </linearGradient></defs>
          </svg>
          <div className="num">{me.day.toLocaleString('fa-IR')}</div>
        </div>
        <div>
          <div className="t1">{seasonName}</div>
          <div className="t2">روز {me.day.toLocaleString('fa-IR')} از {me.season_length.toLocaleString('fa-IR')}</div>
        </div>
      </div>

      <div className="card up u1">
        <div className="me-row">
          {me.profile_image ? (
            <button type="button" className="ava profile-image-trigger"
                    aria-label={`نمایش تصویر پروفایل ${me.name}`}
                    onClick={() => { haptic(); setProfileImageOpen(true); }}>
              <img src={me.profile_image} alt="" />
            </button>
          ) : <div className="ava">{me.name.charAt(0)}</div>}
          <div>
            <div className="nm">{me.name}{me.house ? <span className="house-tag">خاندان {me.house}</span> : null}{me.title ? <span className="title-tag">{me.title}</span> : null}</div>
            <div className="hs">
              {me.admin_spectator
                ? 'حالت نظارت ادمین · بدون قلعه و اقلیم'
                : <>{castleLabel(me.castle)}{me.castles?.length ? ` + ${me.castles.length.toLocaleString('fa-IR')} قلعهٔ دیگر` : ''} · {me.region_name}{me.is_port ? ' · بندر' : ''}</>}
            </div>
            {me.rank != null ? (
              <div className="rk">
                رتبهٔ {me.rank.toLocaleString('fa-IR')} از {me.total_players.toLocaleString('fa-IR')} لرد
                {me.rank_label && RANK_LABEL_FA[me.rank_label] ? ` · ${RANK_LABEL_FA[me.rank_label]}` : ''}
              </div>
            ) : null}
          </div>
        </div>
        <div className="stats">
          <div className="st"><div className="v">{(me.active_campaigns ?? 0).toLocaleString('fa-IR')}</div><div className="k">لشکر در میدان</div></div>
          <div className="st"><div className="v">{me.points.toLocaleString('fa-IR')}</div><div className="k">امتیاز</div></div>
          <div className="st"><div className="v">{(me.admin_spectator ? 0 : 1 + (me.castles?.length ?? 0)).toLocaleString('fa-IR')}</div><div className="k">قلعه</div></div>
          <div className="st"><div className="v">{(me.alliance_count ?? 0).toLocaleString('fa-IR')}</div><div className="k">اتحاد</div></div>
        </div>
      </div>

      <ProfileImageModal image={profileImageOpen ? me.profile_image : null} name={me.name}
                         onClose={() => setProfileImageOpen(false)} />

      <div className="sect up u2">مدال‌ها و افتخارات</div>
      <div className="medal-showcase card up u2">
        {(me.medals || []).length ? me.medals.map(m => {
          const tierName = m.tier === 'gold' ? 'طلا' : m.tier === 'silver' ? 'نقره' : 'برنز';
          const isSpecial = String(m.key || '').startsWith('special_');
          const details = m.reason || m.title || `مدال ${tierName}`;
          return (
            <article key={m.key} className={`player-medal tier-${m.tier} ${isSpecial ? 'special' : ''}`}
                     title={`${m.name} — ${details}`}>
              <div className="player-medal-icon">{m.icon || '🏅'}</div>
              <div className="player-medal-name">{m.name}</div>
              <div className="player-medal-tier">{isSpecial ? 'ویژهٔ ادمین' : tierName}</div>
              {m.title && <div className="player-medal-title">{m.title}</div>}
              {m.reason && <div className="player-medal-reason">{m.reason}</div>}
            </article>
          );
        }) : <div style={{ opacity: .65, padding: 8 }}>هنوز مدالی کسب نکرده‌ای.</div>}
      </div>

      <div className="sect up u2">خزانه و انبار</div>
      <div className="card up u2">
        {Object.entries(RES_META).map(([k, m]) => {
          const v = me.resources[k] ?? 0;
          const cap = me.resource_caps?.[k] ?? m.max;
          const pct = Math.round((v / cap) * 100);
          return (
            <div className="res" key={k}>
              <div className="ic"><m.Icon s={18} /></div>
              <div className="n">{m.name}<small>{m.d}</small></div>
              <div className={`bar ${pct < 35 ? 'low' : ''}`}><i style={{ width: pct + '%' }} /></div>
              <div className="val">{v.toLocaleString('fa-IR')} / {cap.toLocaleString('fa-IR')}</div>
            </div>
          );
        })}
      </div>

      <div className="sect up u2">تسلیحات</div>
      <div className="card up u2">
        {Object.entries(WEAPON_META).map(([k, m]) => {
          const v = me.resources[k] ?? 0;
          const cap = me.resource_caps?.[k] ?? m.max;
          const pct = Math.round((v / cap) * 100);
          return (
            <div className="res" key={k}>
              <div className="ic"><Swords s={18} /></div>
              <div className="n">{WEAPON_NAMES[k]}<small>{m.d}</small></div>
              <div className={`bar ${pct < 35 ? 'low' : ''}`}><i style={{ width: pct + '%' }} /></div>
              <div className="val">{v.toLocaleString('fa-IR')} / {cap.toLocaleString('fa-IR')}</div>
            </div>
          );
        })}
      </div>

      <div className="sect up u2">محبوبیت و مالیات</div>
      <div className="card up u2">
        <div className="res">
          <div className="ic"><Popularity s={18} /></div>
          <div className="n">محبوبیت<small>با برگزاری ضیافت در دیپلماسی بالا می‌رود</small></div>
          <div className="bar"><i style={{ width: (me.popularity ?? 0) + '%' }} /></div>
          <div className="val">{(me.popularity ?? 0).toLocaleString('fa-IR')}٪</div>
        </div>
        <div className="tax-row">
          <span>نرخ مالیات</span>
          <div className="tax-stepper">
            <button type="button" aria-label="کاهش نرخ مالیات" disabled={taxBusy || me.tax_rate <= 0} onClick={() => changeTax(-1)}>−</button>
            <b>{me.tax_rate.toLocaleString('fa-IR')}٪</b>
            <button type="button" aria-label="افزایش نرخ مالیات" disabled={taxBusy || me.tax_rate >= 100} onClick={() => changeTax(1)}>+</button>
          </div>
        </div>
        {rebellion && (
          <div className="page-sub" style={{ marginTop: 7, lineHeight: 1.9 }}>
            آستانهٔ مالیات سنگین با محبوبیت فعلی: <b>{rebellion.tax_heavy_threshold.toLocaleString('fa-IR')}٪</b>
            {' · '}اثر مالیات فعلی در بررسی روزانه: <b style={{ color: rebellion.tax_daily_popularity < 0 ? 'var(--danger)' : 'var(--az2)' }}>
              {rebellion.tax_daily_popularity > 0 ? '+' : ''}{rebellion.tax_daily_popularity.toLocaleString('fa-IR')} محبوبیت
            </b>
            <br />
            درآمد تخمینی همین مالیات: {rebellion.estimated_tax_gold_per_day.toLocaleString('fa-IR')} طلا در روز
            {' · '}بازده مالیات با محبوبیت فعلی: {rebellion.tax_yield_percent.toLocaleString('fa-IR')}٪
          </div>
        )}
        {rebellion && (
          <>
            <div style={{ marginTop: 14 }}>
              <label className="f">سهم غله مردم</label>
              <select value={rebellion.ration} disabled={rationBusy} onChange={e => changeRation(e.target.value)}>
                {Object.entries(rebellion.ration_levels || {}).map(([key, level]) => (
                  <option key={key} value={key}>
                    {level.label} — {Math.round(level.multiplier * 100).toLocaleString('fa-IR')}٪ مصرف · {level.popularity >= 0 ? '+' : ''}{level.popularity.toLocaleString('fa-IR')} محبوبیت
                  </option>
                ))}
              </select>
              <div className="page-sub" style={{ marginTop: 6 }}>
                مصرف روزانهٔ این سهم: حدود {rebellion.ration_food_per_day.toLocaleString('fa-IR')} غله
                {' · '}اثر غله: {rebellion.ration_daily_popularity > 0 ? '+' : ''}{rebellion.ration_daily_popularity.toLocaleString('fa-IR')} محبوبیت
                <br />
                جمع اثر مالیات و غله در بررسی روزانه: <b style={{ color: rebellion.combined_daily_popularity < 0 ? 'var(--danger)' : 'var(--az2)' }}>
                  {rebellion.combined_daily_popularity > 0 ? '+' : ''}{rebellion.combined_daily_popularity.toLocaleString('fa-IR')} محبوبیت
                </b>
                <br />
                احتمال شورش در بررسی روزانه: {rebellion.chance.toLocaleString('fa-IR')}٪ · حد امن {rebellion.safe_popularity.toLocaleString('fa-IR')} · شورش قطعی زیر {rebellion.guaranteed_popularity.toLocaleString('fa-IR')}
              </div>
            </div>
            {rebellion.active && (
              <div style={{ marginTop: 14, padding: 12, borderRadius: 12, background: 'rgba(180,35,35,.14)', border: '1px solid rgba(255,90,90,.35)' }}>
                <div style={{ fontWeight: 900, color: 'var(--danger)' }}>🔥 شورش در قلمرو</div>
                <div className="page-sub" style={{ marginTop: 6 }}>
                  مهلت ارسال رول: {new Date(rebellion.active.deadline).toLocaleString('fa-IR')}
                </div>
                {rebellion.active.status === 'awaiting_roleplay' ? (
                  <>
                    <textarea rows={5} value={rebellionText} onChange={e => setRebellionText(e.target.value)}
                              placeholder="سناریوی برخورد، مذاکره یا سرکوب شورش را بنویس..." />
                    <button className="btn" style={{ marginTop: 10 }} disabled={rebellionBusy} onClick={submitRebellion}>
                      {rebellionBusy ? 'در حال ارسال...' : 'ارسال رول شورش'}
                    </button>
                  </>
                ) : (
                  <div style={{ marginTop: 8 }}>رول تو ثبت شده و منتظر نتیجه ادمین است.</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <div className="sect up u3">فرمان‌ها</div>
      <div className="qgrid up u3">
        <button type="button" className="rbtn q" onClick={() => { haptic(); goTo(1); }}><div className="qi"><Build s={19} /></div>ساختمان‌ها</button>
        <button type="button" className="rbtn q" onClick={() => { haptic(); goTo(2); }}><div className="qi"><Swords s={19} /></div>لشکرکشی</button>
        <button type="button" className="rbtn q" onClick={() => { haptic(); goTo(7); }}><div className="qi"><Eye s={19} /></div>جاسوسی</button>
        <button type="button" className="rbtn q" onClick={() => { haptic(); goTo(5); }}><div className="qi"><Heart s={19} /></div>دیپلماسی</button>
      </div>
    </>
  );
}
