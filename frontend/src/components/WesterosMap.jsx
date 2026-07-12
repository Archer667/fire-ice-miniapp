import { useState } from 'react';
import { haptic } from '../telegram.js';
import { Ship, Keep } from './Icons.jsx';
import { MAP_IMAGE, REGION_COORDS } from '../mapCoords.js';
import ZoomPanMap from './ZoomPanMap.jsx';

/** تصویر نقشه + پین‌های قلعه/شهرهای دارای مختصات — هم برای نمایش (کلیک روی پین)
 * و هم برای حالت ادمین (کلیک روی خودِ نقشه برای گرفتن مختصات یک نقطهٔ خالی) به کار می‌رود.
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
               className={`pin sm ${c.port ? 'port' : ''} ${c.owner ? 'owned' : ''} ${c.mine ? 'mine' : ''} ${pin === c.name ? 'active' : ''}`}
               style={{ left: xy[0] + '%', top: xy[1] + '%', pointerEvents: onPinClick ? 'auto' : 'none' }}
               onClick={(e) => {
                 if (!onPinClick) return; // حالت ادمین: نباید کلیکِ گذاشتنِ پینِ تازه را قورت بدهد
                 e.stopPropagation(); haptic(); onPinClick(c);
               }}>
            <span className="dot">{c.port ? <Ship s={8} /> : <Keep s={8} />}</span>
          </div>
        );
      })}
    </div>
  );
}

/** نقشهٔ یک‌پارچهٔ کل وستروس — بدون تب اقلیم‌ها، فقط خودِ نقشه با آیکن قلعه/شهرهایی
 * که مختصات دارند (بقیه تا وقتی ادمین جایشان را روی نقشه مشخص نکند دیده نمی‌شوند).
 * data: { regions: [{ id, name, castles: [{name, owner, port, coords?}], coords? }] }
 * هر castle می‌تواند owner را به‌صورت { name, points, title, overlord_name } داشته باشد */
export default function WesterosMap({ data, meCastle, onSelectTarget, pickLabel = 'انتخاب به‌عنوان مقصد' }) {
  const [pin, setPin] = useState(null);

  const mapped = data.regions.flatMap(r => {
    const coords = { ...(REGION_COORDS[r.id] || {}), ...(r.coords || {}) };
    return r.castles
      .map(c => ({ ...c, region: r.id, mine: c.name === meCastle, xy: coords[c.name] }))
      .filter(c => c.xy);
  });
  const coords = Object.fromEntries(mapped.map(c => [c.name, c.xy]));
  const active = mapped.find(c => c.name === pin);

  if (mapped.length === 0) return null;

  return (
    <div className="mapview">
      <ZoomPanMap>
        <MapFrame region={{ castles: mapped }} coords={coords} pin={pin}
                  onPinClick={(c) => { haptic(); setPin(pin === c.name ? null : c.name); }} />
      </ZoomPanMap>
      {active && (
        <div className="pin-info">
          <div className="pi-name">{active.name}{active.port ? ' ⚓' : ''}{active.mine ? <span className="pi-mine">قلعهٔ خودت</span> : null}</div>
          {active.owner ? (
            <div className="pi-owner-block">
              <div className="pi-owner">صاحب: {active.owner.name}{active.owner.title ? ` · ${active.owner.title}` : ''}</div>
              <div className="pi-stats">
                امتیاز: {(active.owner.points ?? 0).toLocaleString('fa-IR')}
                {active.owner.overlord_name ? ` · بالادستی: ${active.owner.overlord_name}` : ''}
              </div>
            </div>
          ) : <div className="pi-owner">بدون لرد — خالی</div>}
          {onSelectTarget && (
            <button className="btn ghost pi-pick" onClick={() => onSelectTarget(active)}>{pickLabel}</button>
          )}
        </div>
      )}
    </div>
  );
}
