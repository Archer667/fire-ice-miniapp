import { useState } from 'react';
import { haptic } from '../telegram.js';
import { Ship, Keep, Back } from './Icons.jsx';
import { MAP_IMAGE, REGION_COORDS } from '../mapCoords.js';
import { REGIONS_STATIC } from '../gamedata.js';

/** تصویر نقشه + پین‌های یک اقلیم — هم برای نمایش (کلیک روی پین) و هم برای
 * حالت ادمین (کلیک روی خودِ نقشه برای گرفتن مختصات یک نقطهٔ خالی) به کار می‌رود.
 * مختصات هر قلعه درصدی از عرض/ارتفاع کامل تصویر است (۰ تا ۱۰۰) */
export function MapFrame({ region, coords, pin, onPinClick, onFrameClick }) {
  const handleFrameClick = (e) => {
    if (!onFrameClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xPct = ((e.clientX - rect.left) / rect.width) * 100;
    const yPct = ((e.clientY - rect.top) / rect.height) * 100;
    onFrameClick(Math.max(0, Math.min(100, xPct)), Math.max(0, Math.min(100, yPct)));
  };

  return (
    <div className="mapview-frame" onClick={handleFrameClick} style={{ cursor: onFrameClick ? 'crosshair' : 'default' }}>
      <img src={MAP_IMAGE} alt="نقشهٔ وستروس" draggable={false} />
      {region.castles.map(c => {
        const xy = coords[c.name];
        if (!xy) return null;
        return (
          <div key={c.name}
               className={`pin ${c.port ? 'port' : ''} ${c.owner ? 'owned' : ''} ${c.mine ? 'mine' : ''} ${pin === c.name ? 'active' : ''}`}
               style={{ left: xy[0] + '%', top: xy[1] + '%' }}
               onClick={(e) => { e.stopPropagation(); haptic(); onPinClick?.(c); }}>
            <span className="dot">{c.port ? <Ship s={11} /> : <Keep s={11} />}</span>
          </div>
        );
      })}
    </div>
  );
}

/** نقشهٔ کامل با لیست اقلیم‌های قابل‌بازشدن — برای سکشن نقشهٔ صفحهٔ لشکرکشی.
 * data: { regions: [{ id, name, castles: [{name, owner, port, coords?, mine?}] }] }
 * هر castle می‌تواند owner را به‌صورت { name, points, title, overlord_name } داشته باشد */
export default function WesterosMap({ data, meCastle, onSelectTarget }) {
  const [open, setOpen] = useState(null);
  const [pin, setPin] = useState(null);

  const toggleRegion = (rid) => {
    haptic();
    setPin(null);
    setOpen(open === rid ? null : rid);
  };

  return (
    <div>
      {data.regions.map(r => {
        const coords = { ...(REGION_COORDS[r.id] || {}), ...(r.coords || {}) };
        const hasMap = Object.keys(coords).length > 0;
        const castles = r.castles.map(c => ({ ...c, mine: c.name === meCastle }));
        return (
          <div key={r.id}>
            <div className={`region ${open === r.id ? 'open' : ''}`} onClick={() => toggleRegion(r.id)}>
              <div className="g">{REGIONS_STATIC[r.id]?.g || '—'}</div>
              <div className="n">{r.name}
                <small>{castles.filter(c => c.owner).length.toLocaleString('fa-IR')} قلعهٔ دارای لرد از {castles.length.toLocaleString('fa-IR')}
                  {!hasMap ? ' · نقشهٔ تصویری به‌زودی' : ''}</small>
              </div>
              <span className="arrow"><Back s={16} /></span>
            </div>

            {open === r.id && hasMap && (
              <div className="mapview">
                <MapFrame region={{ ...r, castles }} coords={coords} pin={pin}
                          onPinClick={(c) => setPin(pin === c.name ? null : c.name)} />
                {pin && (() => {
                  const c = castles.find(x => x.name === pin);
                  if (!c) return null;
                  return (
                    <div className="pin-info">
                      <div className="pi-name">{c.name}{c.port ? ' ⚓' : ''}{c.mine ? <span className="pi-mine">قلعهٔ خودت</span> : null}</div>
                      {c.owner ? (
                        <div className="pi-owner-block">
                          <div className="pi-owner">صاحب: {c.owner.name}{c.owner.title ? ` · ${c.owner.title}` : ''}</div>
                          <div className="pi-stats">
                            امتیاز: {(c.owner.points ?? 0).toLocaleString('fa-IR')}
                            {c.owner.overlord_name ? ` · بالادستی: ${c.owner.overlord_name}` : ''}
                          </div>
                        </div>
                      ) : <div className="pi-owner">بدون لرد — خالی</div>}
                      {onSelectTarget && (
                        <button className="btn ghost pi-pick" onClick={() => onSelectTarget(c)}>انتخاب به‌عنوان مقصد</button>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}

            {open === r.id && !hasMap && (
              <div className="region-castles">
                {castles.map(c => (
                  <div className="rc" key={c.name} onClick={() => onSelectTarget?.(c)} style={{ cursor: onSelectTarget ? 'pointer' : 'default' }}>
                    <span>{c.name}{c.port ? ' ⚓' : ''}</span>
                    {c.owner
                      ? <span className="own">{c.owner.name}</span>
                      : <span className="empty">بدون لرد</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
