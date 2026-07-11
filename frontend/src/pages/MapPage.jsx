import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Swords, Keep, Ship } from '../components/Icons.jsx';
import { MAP_IMAGE, REGION_COORDS } from '../mapCoords.js';
import ZoomPanMap from '../components/ZoomPanMap.jsx';

export default function MapPage() {
  const { me, toast } = useGame();
  const [data, setData] = useState(null);
  const [pin, setPin] = useState(null);

  useEffect(() => { api.map().then(setData).catch(e => toast(e.message)); }, []);

  if (!data) return <div className="loading">نقشه در حال گشوده‌شدن...</div>;

  const pinned = data.regions
    .flatMap(r => r.castles.map(c => ({ ...c, xy: c.pin || REGION_COORDS[r.id]?.[c.name] })))
    .filter(c => c.xy);

  const active = pinned.find(c => c.name === pin);

  return (
    <>
      <div className="page-title up">نقشهٔ وستروس</div>
      <div className="page-sub up">لشکرکشی‌ها ۱۵ دقیقه پس از فرمان، برای همه آشکار می‌شوند</div>

      <div className="up u1">
        {data.campaigns.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
            هیچ لشکری در حرکت نیست — وستروس در آرامشی مشکوک است
          </div>
        )}
        {data.campaigns.map((c, i) => (
          <div key={i} className={`warband ${c.mine ? 'mine' : ''}`}>
            <div className="wi"><Swords s={17} /></div>
            <div className="t">
              <b>لشکری از {c.from}</b> به‌سوی <b>{c.to}</b> در حرکت است
              <div className="tm">{c.mine ? 'فرمان تو — در انتظار داوری' : `آشکار شده — ${Math.max(0, c.revealed_minutes_ago).toLocaleString('fa-IR')} دقیقه پیش`}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="up u2">
        <div className="mapview" onClick={() => setPin(null)}>
          <ZoomPanMap>
            <div className="mapview-frame">
              <img src={MAP_IMAGE} alt="نقشهٔ وستروس" draggable={false} />
              {pinned.map(c => {
                const mine = c.name === me.castle;
                return (
                  <div key={c.name}
                       className={`pin sm ${c.port ? 'port' : ''} ${c.owner ? 'owned' : ''} ${mine ? 'mine' : ''} ${pin === c.name ? 'active' : ''}`}
                       style={{ left: c.xy[0] + '%', top: c.xy[1] + '%' }}
                       onClick={(e) => { e.stopPropagation(); haptic(); setPin(pin === c.name ? null : c.name); }}>
                    <span className="dot">{c.port ? <Ship s={8} /> : <Keep s={8} />}</span>
                  </div>
                );
              })}
            </div>
          </ZoomPanMap>
          {active && (
            <div className="pin-info">
              <div className="pi-name">{active.name}{active.port ? ' ⚓' : ''}{active.name === me.castle ? <span className="pi-mine">قلعهٔ خودت</span> : null}</div>
              <div className="pi-owner">{active.owner ? `صاحب: ${active.owner}` : 'بدون لرد — خالی'}</div>
            </div>
          )}
        </div>
        {pinned.length === 0 && (
          <div className="card" style={{ textAlign: 'center', color: 'var(--mid)', fontSize: 12.5 }}>
            هنوز هیچ قلعه/شهری روی نقشه نشانه‌گذاری نشده
          </div>
        )}
      </div>
    </>
  );
}
