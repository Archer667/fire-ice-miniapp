import { useEffect, useState } from 'react';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { api } from '../api.js';
import { Coin, Wheat, People, Pick, Rock, Wood, Wine, Build, Swords, Eye, Heart, Popularity, Blossom, SunIcon, Leaf, Snowflake, Gift } from '../components/Icons.jsx';
import { SEASONS, seasonOf } from '../seasons.js';
import { WEAPON_NAMES } from '../gamedata.js';

const SEASON_ICON = { spring: Blossom, summer: SunIcon, autumn: Leaf, winter: Snowflake };

const RES_META = {
  gold:  { name: 'طلا', d: 'معدن طلا · بازار', Icon: Coin,  max: 2000 },
  food:  { name: 'غذا', d: 'مزرعه · دامداری', Icon: Wheat, max: 2000 },
  men:   { name: 'نیروی انسانی', d: 'ظرفیت استخدام', Icon: People, max: 1000 },
  wood:  { name: 'چوب', d: 'چوب‌بری', Icon: Wood, max: 800 },
  iron:  { name: 'آهن', d: 'معدن آهن', Icon: Pick, max: 500 },
  stone: { name: 'سنگ', d: 'معدن سنگ', Icon: Rock, max: 500 },
  wine:  { name: 'شراب', d: 'می‌کده · ضیافت و پیمان‌ها', Icon: Wine, max: 300 },
};

const WEAPON_META = {
  weapon_sword:  { d: 'کارگاه تسلیحات پیاده‌نظام', max: 300 },
  weapon_spear:  { d: 'کارگاه تسلیحات نیزه‌داران', max: 300 },
  weapon_archer: { d: 'کارگاه تسلیحات کمانداران', max: 300 },
  weapon_lcav:   { d: 'کارگاه تسلیحات سوارهٔ سبک', max: 200 },
  weapon_hcav:   { d: 'کارگاه تسلیحات سوارهٔ سنگین', max: 200 },
};

const RANK_LABEL_FA = { overlord: 'بالادستی اقلیم', warden: 'والی', king: 'پادشاه/ملکه' };

export default function Dashboard({ goTo }) {
  const { me, setMe, toast } = useGame();
  const dayPct = Math.round((me.day / me.season_length) * 100);
  const C = 2 * Math.PI * 19;
  const [taxBusy, setTaxBusy] = useState(false);
  const season = seasonOf(me.day);
  const { name: seasonName, from: seasonFrom, to: seasonTo } = SEASONS[season];
  const SeasonIcon = SEASON_ICON[season];

  const [daily, setDaily] = useState(null);
  const [dailyBusy, setDailyBusy] = useState(false);
  useEffect(() => { api.dailyStatus().then(setDaily).catch(() => {}); }, []);

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

  const changeTax = async (delta) => {
    const rate = Math.max(0, Math.min(me.max_tax_rate, me.tax_rate + delta));
    if (rate === me.tax_rate) return;
    setTaxBusy(true);
    try {
      await api.setTax(rate);
      haptic();
      setMe({ ...me, tax_rate: rate });
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
          <div className="ava">{me.name.charAt(0)}</div>
          <div>
            <div className="nm">{me.name}{me.title ? <span className="title-tag">{me.title}</span> : null}</div>
            <div className="hs">{me.castle} · {me.region_name}{me.is_port ? ' · بندر' : ''}</div>
            <div className="rk">
              رتبهٔ {me.rank.toLocaleString('fa-IR')} از {me.total_players.toLocaleString('fa-IR')} لرد
              {me.rank_label && RANK_LABEL_FA[me.rank_label] ? ` · ${RANK_LABEL_FA[me.rank_label]}` : ''}
            </div>
          </div>
        </div>
        <div className="stats">
          <div className="st"><div className="v">{(me.active_campaigns ?? 0).toLocaleString('fa-IR')}</div><div className="k">لشکر در میدان</div></div>
          <div className="st"><div className="v">{me.points.toLocaleString('fa-IR')}</div><div className="k">امتیاز</div></div>
          <div className="st"><div className="v">۱</div><div className="k">قلعه</div></div>
          <div className="st"><div className="v">{(me.alliance_count ?? 0).toLocaleString('fa-IR')}</div><div className="k">اتحاد</div></div>
        </div>
      </div>

      <div className="sect up u2">خزانه و انبار</div>
      <div className="card up u2">
        {Object.entries(RES_META).map(([k, m]) => {
          const v = me.resources[k] ?? 0;
          const pct = Math.round((v / m.max) * 100);
          return (
            <div className="res" key={k}>
              <div className="ic"><m.Icon s={18} /></div>
              <div className="n">{m.name}<small>{m.d}</small></div>
              <div className={`bar ${pct < 35 ? 'low' : ''}`}><i style={{ width: pct + '%' }} /></div>
              <div className="val">{v.toLocaleString('fa-IR')}</div>
            </div>
          );
        })}
      </div>

      <div className="sect up u2">تسلیحات</div>
      <div className="card up u2">
        {Object.entries(WEAPON_META).map(([k, m]) => {
          const v = me.resources[k] ?? 0;
          const pct = Math.round((v / m.max) * 100);
          return (
            <div className="res" key={k}>
              <div className="ic"><Swords s={18} /></div>
              <div className="n">{WEAPON_NAMES[k]}<small>{m.d}</small></div>
              <div className={`bar ${pct < 35 ? 'low' : ''}`}><i style={{ width: pct + '%' }} /></div>
              <div className="val">{v.toLocaleString('fa-IR')}</div>
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
          <span>نرخ مالیات <small>(سقف {me.max_tax_rate.toLocaleString('fa-IR')}٪ با این محبوبیت)</small></span>
          <div className="tax-stepper">
            <button type="button" aria-label="کاهش نرخ مالیات" disabled={taxBusy || me.tax_rate <= 0} onClick={() => changeTax(-1)}>−</button>
            <b>{me.tax_rate.toLocaleString('fa-IR')}٪</b>
            <button type="button" aria-label="افزایش نرخ مالیات" disabled={taxBusy || me.tax_rate >= me.max_tax_rate} onClick={() => changeTax(1)}>+</button>
          </div>
        </div>
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
