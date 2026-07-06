import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useGame } from '../store.jsx';
import { haptic } from '../telegram.js';
import { Swords, Back } from '../components/Icons.jsx';
import { REGIONS_STATIC } from '../gamedata.js';

export default function MapPage() {
  const { toast } = useGame();
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => { api.map().then(setData).catch(e => toast(e.message)); }, []);

  if (!data) return <div className="loading">نقشه در حال گشوده‌شدن...</div>;

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

      <div className="sect up u2">اقلیم‌های نُه‌گانه</div>
      <div className="up u2">
        {data.regions.map(r => (
          <div key={r.id}>
            <div className={`region ${open === r.id ? 'open' : ''}`}
                 onClick={() => { haptic(); setOpen(open === r.id ? null : r.id); }}>
              <div className="g">{REGIONS_STATIC[r.id]?.g || '—'}</div>
              <div className="n">{r.name}
                <small>{r.castles.filter(c => c.owner).length.toLocaleString('fa-IR')} قلعهٔ دارای لرد از {r.castles.length.toLocaleString('fa-IR')}</small>
              </div>
              <span className="arrow"><Back s={16} /></span>
            </div>
            {open === r.id && (
              <div className="region-castles">
                {r.castles.map(c => (
                  <div className="rc" key={c.name}>
                    <span>{c.name}{c.port ? ' ⚓' : ''}</span>
                    {c.owner
                      ? <span className="own">{c.owner}</span>
                      : <span className="empty">بدون لرد</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
