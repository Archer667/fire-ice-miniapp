import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Coin, Wheat, People, Pick, Rock, Build, Swords, Eye, Heart } from '../components/Icons.jsx';

const RES_META = {
  gold:  { name: 'طلا', d: 'معدن طلا · بازار', Icon: Coin,  max: 2000 },
  food:  { name: 'غذا', d: 'مزرعه · دامداری', Icon: Wheat, max: 2000 },
  men:   { name: 'نیروی انسانی', d: 'ظرفیت استخدام', Icon: People, max: 1000 },
  iron:  { name: 'آهن', d: 'معدن آهن', Icon: Pick, max: 500 },
  stone: { name: 'سنگ', d: 'معدن سنگ', Icon: Rock, max: 500 },
};

export default function Dashboard({ goTo }) {
  const { me, toast } = useGame();
  const dayPct = Math.round((me.day / me.season_length) * 100);
  const C = 2 * Math.PI * 19;

  return (
    <>
      <div className="season up">
        <div className="ring">
          <svg width="46" height="46" viewBox="0 0 46 46">
            <circle cx="23" cy="23" r="19" fill="none" stroke="rgba(160,195,255,0.12)" strokeWidth="4" />
            <circle cx="23" cy="23" r="19" fill="none" stroke="url(#gr)" strokeWidth="4"
                    strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - dayPct / 100)} />
            <defs><linearGradient id="gr" x1="0" y1="0" x2="1" y2="1">
              <stop stopColor="#38bdf8" /><stop offset="1" stopColor="#4da3ff" />
            </linearGradient></defs>
          </svg>
          <div className="num">{me.day.toLocaleString('fa-IR')}</div>
        </div>
        <div>
          <div className="t1">زمستان نزدیک است</div>
          <div className="t2">روز {me.day.toLocaleString('fa-IR')} از {me.season_length.toLocaleString('fa-IR')} · دورهٔ نخست</div>
        </div>
      </div>

      <div className="card up u1">
        <div className="me-row">
          <div className="ava">{me.name.charAt(0)}</div>
          <div>
            <div className="nm">{me.name}</div>
            <div className="hs">{me.castle} · {me.region_name}{me.is_port ? ' · بندر' : ''}</div>
            <div className="rk">رتبهٔ {me.rank.toLocaleString('fa-IR')} از {me.total_players.toLocaleString('fa-IR')} لرد</div>
          </div>
        </div>
        <div className="stats">
          <div className="st"><div className="v">{Object.values(me.troops || {}).reduce((a, b) => a + b, 0).toLocaleString('fa-IR')}</div><div className="k">سپاه</div></div>
          <div className="st"><div className="v">{me.points.toLocaleString('fa-IR')}</div><div className="k">امتیاز</div></div>
          <div className="st"><div className="v">۱</div><div className="k">قلعه</div></div>
          <div className="st"><div className="v">۰</div><div className="k">اتحاد</div></div>
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

      <div className="sect up u3">فرمان‌ها</div>
      <div className="qgrid up u3">
        <div className="q" onClick={() => { haptic(); goTo(1); }}><div className="qi"><Build s={19} /></div>ساختمان‌ها</div>
        <div className="q" onClick={() => { haptic(); goTo(3); }}><div className="qi"><Swords s={19} /></div>لشکرکشی</div>
        <div className="q" onClick={() => toast('جاسوسی — فاز ۲')}><div className="qi"><Eye s={19} /></div>جاسوسی</div>
        <div className="q" onClick={() => toast('دیپلماسی — فاز ۲')}><div className="qi"><Heart s={19} /></div>دیپلماسی</div>
      </div>
    </>
  );
}
