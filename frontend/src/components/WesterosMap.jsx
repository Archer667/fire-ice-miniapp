import { useState } from 'react';
import { haptic } from '../telegram.js';
import { Ship, Keep, Build, Rock } from './Icons.jsx';
import { MAP_IMAGE, REGION_COORDS } from '../mapCoords.js';
import { REGIONS_STATIC } from '../gamedata.js';
import ZoomPanMap from './ZoomPanMap.jsx';

const KIND_ICON = { castle: Keep, city: Build, ruin: Rock, port: Ship };

/** تصویر نقشه + پین‌های قلعه/شهرهای دارای مختصات — هم برای نمایش (کلیک روی پین،
 * با تب کوچک اطلاعات دقیقاً کنار همان پین) و هم برای حالت ادمین (کلیک روی خودِ
 * نقشه برای گرفتن مختصات یک نقطهٔ خالی) به کار می‌رود.
 * مختصات هر قلعه درصدی از عرض/ارتفاع کامل تصویر است (۰ تا ۱۰۰) */
export function MapFrame({ region, coords, pin, onPinClick, onFrameClick, onSelectTarget, pickLabel }) {
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
        const Icon = KIND_ICON[c.kind] || (c.port ? Ship : Keep);
        const active = pin === c.name;
        const popupStyle = xy[1] < 30
          ? { top: '100%', bottom: 'auto', marginTop: 10, marginBottom: 0 }
          : {};
        if (xy[0] < 20) Object.assign(popupStyle, { left: 0, transform: 'none' });
        else if (xy[0] > 80) Object.assign(popupStyle, { left: 'auto', right: 0, transform: 'none' });
        return (
          <div key={c.name}
               className={`pin sm ${c.port ? 'port' : ''} ${c.owner ? 'owned' : ''} ${c.mine ? 'mine' : ''} ${active ? 'active' : ''}`}
               style={{ left: xy[0] + '%', top: xy[1] + '%', pointerEvents: onPinClick ? 'auto' : 'none' }}
               onClick={(e) => {
                 if (!onPinClick) return; // حالت ادمین: نباید کلیکِ گذاشتنِ پینِ تازه را قورت بدهد
                 e.stopPropagation(); haptic(); onPinClick(c);
               }}>
            <span className="dot"><Icon s={8} /></span>
            {active && onPinClick && (
              <div className="pin-popup" style={popupStyle} onClick={(e) => e.stopPropagation()}>
                <div className="pi-name">{c.name}{c.port ? ' ⚓' : ''}{c.mine ? <span className="pi-mine">قلعهٔ خودت</span> : null}</div>
                <div className="pi-owner">اقلیم: {REGIONS_STATIC[c.region]?.name || '—'}</div>
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
                  <button className="btn ghost pi-pick" onClick={() => onSelectTarget(c)}>{pickLabel}</button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** نقشهٔ یک‌پارچهٔ کل وستروس — بدون تب اقلیم‌ها، فقط خودِ نقشه با آیکن قلعه/شهرهایی
 * که مختصات دارند (بقیه تا وقتی ادمین جایشان را روی نقشه مشخص نکند دیده نمی‌شوند).
 * data: { regions: [{ id, name, castles: [{name, owner, port, kind, coords?}], coords? }] }
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

  if (mapped.length === 0) return null;

  return (
    <div className="mapview">
      <ZoomPanMap>
        <MapFrame region={{ castles: mapped }} coords={coords} pin={pin}
                  onPinClick={(c) => { haptic(); setPin(pin === c.name ? null : c.name); }}
                  onSelectTarget={onSelectTarget} pickLabel={pickLabel} />
      </ZoomPanMap>
    </div>
  );
}
