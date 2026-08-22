import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { haptic } from '../telegram.js';
import { Ship, Keep, Coliseum, Swords } from './Icons.jsx';
import { MAP_IMAGE } from '../mapCoords.js';
import { REGIONS_STATIC, castleLabel, REGION_COLORS, PACT_COLORS, ALLIANCE_TYPES, SEA_EDGES, isSeaEdge } from '../gamedata.js';
import ZoomPanMap, { ZoomContext } from './ZoomPanMap.jsx';

/** جای‌گذاری و ضدِمقیاسِ پاپ‌آپ اطلاعات — طوری که همیشه دقیقاً کنار پین بچسبد
 * ولی با زوم نقشه بزرگ/کوچک نشود (اندازه‌اش همیشه یک‌جور و خواناست) */
function popupPlacement(xy, zoom) {
  const vBelow = xy[1] < 30;
  const hSide = xy[0] < 20 ? 'left' : xy[0] > 80 ? 'right' : 'center';
  const style = { transformOrigin: `${hSide === 'center' ? '50%' : hSide === 'left' ? '0%' : '100%'} ${vBelow ? '0%' : '100%'}` };
  style[vBelow ? 'top' : 'bottom'] = '100%';
  style[vBelow ? 'bottom' : 'top'] = 'auto';
  style.marginTop = vBelow ? 10 : 0;
  style.marginBottom = vBelow ? 0 : 10;
  if (hSide === 'center') { style.left = '50%'; style.transform = `translateX(-50%) scale(${1 / zoom})`; }
  else if (hSide === 'left') { style.left = 0; style.transform = `scale(${1 / zoom})`; }
  else { style.left = 'auto'; style.right = 0; style.transform = `scale(${1 / zoom})`; }
  return style;
}

const KIND_ICON = { castle: Keep, city: Keep, ruin: Coliseum, port: Ship };

/** تصویر نقشه + پین‌های قلعه/شهرهای دارای مختصات — هم برای نمایش (کلیک روی پین،
 * با تب کوچک اطلاعات دقیقاً کنار همان پین) و هم برای حالت ادمین (کلیک روی خودِ
 * نقشه برای گرفتن مختصات یک نقطهٔ خالی) به کار می‌رود.
 * مختصات هر قلعه درصدی از عرض/ارتفاع کامل تصویر است (۰ تا ۱۰۰) */
function ArmyMarker({ campaign, coords }) {
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 250);
    return () => clearInterval(timer);
  }, []);

  const points = (campaign.route_path || [campaign.from, campaign.to]).map(n => coords[n]).filter(Boolean);
  if (campaign.arrived || points.length < 2 || !campaign.departed_at || !campaign.arrival_at) return null;
  const start = new Date(campaign.departed_at).getTime();
  const end = new Date(campaign.arrival_at).getTime();
  const progress = Math.max(0, Math.min(1, (tick - start) / Math.max(1, end - start)));
  if (progress >= 1) return null;

  const lengths = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const len = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
    lengths.push(len); total += len;
  }
  let remaining = progress * total;
  let xy = points[points.length - 1];
  for (let i = 0; i < lengths.length; i++) {
    if (remaining <= lengths[i] || i === lengths.length - 1) {
      const part = lengths[i] ? Math.max(0, Math.min(1, remaining / lengths[i])) : 0;
      xy = [
        points[i][0] + (points[i + 1][0] - points[i][0]) * part,
        points[i][1] + (points[i + 1][1] - points[i][1]) * part,
      ];
      break;
    }
    remaining -= lengths[i];
  }
  const color = REGION_COLORS[campaign.owner_region] || '#d8c39a';
  const label = `${campaign.mine ? 'لشکر تو' : `لشکر ${campaign.player_name || 'ناشناس'}`} — ${castleLabel(campaign.from)} به ${castleLabel(campaign.to)}`;
  return (
    <div className={`army-marker ${campaign.mine ? 'mine' : ''}`} style={{ left: `${xy[0]}%`, top: `${xy[1]}%`, '--army-color': color }} title={label} aria-label={label}>
      <span className="army-halo" />
      <span className="army-icon"><Swords s={9} /></span>
    </div>
  );
}

export function MapFrame({ region, coords, pin, onPinClick, onFrameClick, onSelectTarget, pickLabel, colorMode = 'region', routeSegments, seaLaneSegments, campaigns = [] }) {
  const zoom = useContext(ZoomContext);
  const handleFrameClick = (e) => {
    if (!onFrameClick) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xPct = ((e.clientX - rect.left) / rect.width) * 100;
    const yPct = ((e.clientY - rect.top) / rect.height) * 100;
    onFrameClick(Math.max(0, Math.min(100, xPct)), Math.max(0, Math.min(100, yPct)));
  };

  return (
    <div className="map-canvas" onClick={handleFrameClick} style={{ cursor: onFrameClick ? 'crosshair' : 'default' }}>
      <img src={MAP_IMAGE} alt="نقشهٔ وستروس" draggable={false} />
      {(seaLaneSegments?.length > 0 || routeSegments?.length > 0) && (
        <svg className="map-overlay-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          {seaLaneSegments?.map(([[x1, y1], [x2, y2]], i) => (
            <line key={`sl${i}`} className="sea-lane-line" x1={x1} y1={y1} x2={x2} y2={y2} />
          ))}
          {routeSegments?.map((s, i) => (
            <line key={`rt${i}`} className={`route-line ${s.sea ? 'sea' : 'land'}`}
                  x1={s.a[0]} y1={s.a[1]} x2={s.b[0]} y2={s.b[1]} />
          ))}
        </svg>
      )}
      {region.castles.map(c => {
        const xy = coords[c.name];
        if (!xy) return null;
        const Icon = KIND_ICON[c.kind] || (c.port ? Ship : Keep);
        const active = pin === c.name;
        const popupStyle = popupPlacement(xy, zoom);
        const ownerColor = c.owner
          ? (colorMode === 'pact' ? PACT_COLORS[c.owner.pact || 'none'] : (c.owner.region ? REGION_COLORS[c.owner.region] : null))
          : null;
        const dotStyle = ownerColor ? { borderColor: ownerColor, color: ownerColor } : undefined;
        return (
          <div key={c.name} role={onPinClick ? 'button' : undefined} tabIndex={onPinClick ? 0 : undefined}
               aria-label={onPinClick ? c.name : undefined}
               className={`pin sm ${c.port ? 'port' : ''} ${c.owner ? 'owned' : ''} ${c.mine ? 'mine' : ''} ${active ? 'active' : ''}`}
               style={{ left: xy[0] + '%', top: xy[1] + '%', pointerEvents: onPinClick ? 'auto' : 'none' }}
               onClick={(e) => {
                 if (!onPinClick) return; // حالت ادمین: نباید کلیکِ گذاشتنِ پینِ تازه را قورت بدهد
                 e.stopPropagation(); haptic(); onPinClick(c);
               }}
               onKeyDown={(e) => {
                 if (!onPinClick) return;
                 if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); haptic(); onPinClick(c); }
               }}>
            <span className="dot" style={dotStyle}><Icon s={8} /></span>
            {active && onPinClick && (
              <div className="pin-popup" style={popupStyle} onClick={(e) => e.stopPropagation()}>
                <div className="pi-name">{castleLabel(c.name)}{c.port ? ' ⚓' : ''}{c.mine ? <span className="pi-mine">قلعهٔ خودت</span> : null}</div>
                <div className="pi-owner">اقلیم: {REGIONS_STATIC[c.region]?.name || '—'}</div>
                {c.owner ? (
                  <div className="pi-owner-block">
                    <div className="pi-owner">
                      {ownerColor && <span className="pi-swatch" style={{ background: ownerColor }} />}
                      صاحب: {c.owner.name}{c.owner.title ? ` · ${c.owner.title}` : ''}
                      {c.owner.region && REGIONS_STATIC[c.owner.region] ? ` (${REGIONS_STATIC[c.owner.region].name})` : ''}
                    </div>
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
      {campaigns.map(c => <ArmyMarker key={c.id || `${c.from}-${c.to}-${c.departed_at}`} campaign={c} coords={coords} />)}
    </div>
  );
}

/** نقشهٔ کوچکِ کناری — کلِ تصویر در ابعادِ ریز با یه نقطه به‌ازای هر قلعهٔ نمایش‌داده‌شده
 * و یه مستطیلِ روشن که محدودهٔ الان‌دیده‌شده رو نشون می‌ده؛ زدن روی هرجاش نقشهٔ اصلی
 * رو می‌بره همونجا */
function MiniMap({ pins, view, onJump }) {
  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const xPct = ((e.clientX - rect.left) / rect.width) * 100;
    const yPct = ((e.clientY - rect.top) / rect.height) * 100;
    onJump(xPct, yPct);
  };
  const vx = Math.max(0, Math.min(100, view?.x ?? 0));
  const vy = Math.max(0, Math.min(100, view?.y ?? 0));
  const vw = Math.max(0, Math.min(100 - vx, view?.w ?? 100));
  const vh = Math.max(0, Math.min(100 - vy, view?.h ?? 100));
  return (
    <div className="minimap" onClick={handleClick} role="button" aria-label="پرش رویِ نقشهٔ کوچک">
      <img src={MAP_IMAGE} alt="" draggable={false} />
      {pins.map(c => (
        <span key={c.name} className={`minimap-dot ${c.mine ? 'mine' : c.owner ? 'owned' : ''}`}
              style={{ left: c.xy[0] + '%', top: c.xy[1] + '%' }} />
      ))}
      <div className="minimap-viewport" style={{ left: vx + '%', top: vy + '%', width: vw + '%', height: vh + '%' }} />
    </div>
  );
}

/** نقشهٔ یک‌پارچهٔ کل وستروس — پین قلعه/شهرهایی که مختصات دارند، به‌همراه تب‌های
 * میان‌بُرِ اقلیم، نقشهٔ کوچکِ کناری، و دکمهٔ پرش به قلعهٔ خودت.
 * data: { regions: [{ id, name, castles: [{name, owner, port, kind, coords?}], coords? }] }
 * هر castle می‌تواند owner را به‌صورت { name, points, title, overlord_name } داشته باشد */
const PIN_FILTERS = [
  { key: 'all', label: 'همه' },
  { key: 'mine', label: 'قلعهٔ من' },
  { key: 'owned', label: 'صاحب‌دار' },
  { key: 'empty', label: 'خالی' },
  { key: 'port', label: 'بندر' },
];
const PACT_LEGEND_ORDER = ['full_alliance', 'non_aggression', 'trade', 'none'];

export default function WesterosMap({ data, meCastle, meCastles, onSelectTarget, pickLabel = 'انتخاب به‌عنوان مقصد', routePath }) {
  const [pin, setPin] = useState(null);
  const [view, setView] = useState(null);
  const [activeRegion, setActiveRegion] = useState(null);
  const [pinFilter, setPinFilter] = useState('all');
  const [colorMode, setColorMode] = useState('region');
  const mapRef = useRef(null);

  // meCastles همهٔ قلعه‌های خودت رو می‌گیره (خونه + هرچی با فتح/تصمیم ادمین گرفتی)؛
  // meCastle (تکی) هم برای سازگاری با فراخوان‌های قدیمی‌تر هنوز پشتیبانی می‌شه
  const myCastleSet = useMemo(
    () => new Set(meCastles && meCastles.length ? meCastles : (meCastle ? [meCastle] : [])),
    [meCastle, meCastles]
  );

  const regionsMapped = useMemo(() => data.regions.map(r => {
    const rc = r.coords || {};
    const castles = r.castles
      .map(c => ({ ...c, region: r.id, mine: myCastleSet.has(c.name), xy: rc[c.name] }))
      .filter(c => c.xy);
    return { id: r.id, name: r.name, castles };
  }).filter(r => r.castles.length > 0), [data, myCastleSet]);

  const mapped = useMemo(() => regionsMapped.flatMap(r => r.castles), [regionsMapped]);
  const coords = useMemo(() => Object.fromEntries(mapped.map(c => [c.name, c.xy])), [mapped]);
  const terrainOf = useMemo(() => Object.fromEntries(mapped.map(c => [c.name, c.terrain])), [mapped]);

  // خطوطِ کم‌رنگِ یال‌های دریایی — همیشه از رویِ کل پین‌های نقشه‌شده رسم می‌شه (مستقل از فیلترِ پین‌ها)
  const seaLaneSegments = useMemo(() => {
    const segs = [];
    for (const key of SEA_EDGES) {
      const [a, b] = key.split('|');
      if (coords[a] && coords[b]) segs.push([coords[a], coords[b]]);
    }
    return segs;
  }, [coords]);

  // مسیرِ لشکرکشیِ انتخاب‌شده (اگه پاس داده شده باشه) — بخشِ دریایی‌اش رنگ/الگویِ جدا داره
  const routeSegments = useMemo(() => {
    if (!routePath || routePath.length < 2) return [];
    const segs = [];
    for (let i = 0; i < routePath.length - 1; i++) {
      const a = routePath[i], b = routePath[i + 1];
      if (coords[a] && coords[b]) segs.push({ a: coords[a], b: coords[b], sea: isSeaEdge(a, b, (n) => terrainOf[n]) });
    }
    return segs;
  }, [routePath, coords, terrainOf]);

  // محدودهٔ واقعیِ پین‌های هر اقلیم — برای تب‌های میان‌بُر، از خودِ مختصاتِ ثبت‌شده
  // حساب می‌شه (نه یه عدد ثابتِ حدسی)، پس با هر پینِ تازه‌ای که ادمین اضافه کنه خودکار درست می‌مونه
  const regionBoxes = useMemo(() => Object.fromEntries(regionsMapped.map(r => {
    const xs = r.castles.map(c => c.xy[0]), ys = r.castles.map(c => c.xy[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    return [r.id, { x: minX, y: minY, w: Math.max(maxX - minX, 5), h: Math.max(maxY - minY, 5) }];
  })), [regionsMapped]);

  const myPin = mapped.find(c => c.mine);

  // با بازشدنِ صفحه، اگه خودت قلعه داشته باشی، نقشه مستقیم روی محدودهٔ اقلیمِ خودت باز می‌شه
  // (نه یه گوشهٔ دلبخواهیِ نقشهٔ فشرده‌شده) — وگرنه با زوم-به-اندازه (fitZoom) کلِ نقشه دیده می‌شه
  useEffect(() => {
    if (myPin && regionBoxes[myPin.region]) {
      mapRef.current?.flyToBox(regionBoxes[myPin.region]);
      setActiveRegion(myPin.region);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredCastles = useMemo(() => mapped.filter(c => {
    if (pinFilter === 'mine') return c.mine;
    if (pinFilter === 'owned') return !!c.owner;
    if (pinFilter === 'empty') return !c.owner;
    if (pinFilter === 'port') return !!c.port;
    return true;
  }), [mapped, pinFilter]);

  if (mapped.length === 0) return null;

  const ownedRegions = [...new Set(mapped.filter(c => c.owner?.region).map(c => c.owner.region))];
  const pactTypesPresent = colorMode === 'pact'
    ? PACT_LEGEND_ORDER.filter(t => mapped.some(c => c.owner && !c.mine && (c.owner.pact || 'none') === t))
    : [];

  const jumpToRegion = (rid) => {
    haptic();
    setActiveRegion(rid);
    setPin(null);
    mapRef.current?.flyToBox(regionBoxes[rid]);
  };
  const jumpToMine = () => {
    if (!myPin) return;
    haptic();
    setActiveRegion(null);
    setPin(myPin.name);
    mapRef.current?.flyToPoint(myPin.xy[0], myPin.xy[1], 2.4);
  };
  const jumpFromMiniMap = (x, y) => {
    haptic();
    setActiveRegion(null);
    mapRef.current?.flyToPoint(x, y, 2.2);
  };

  return (
    <div className="mapview">
      {regionsMapped.length > 1 && (
        <div className="map-region-tabs">
          {regionsMapped.map(r => (
            <button type="button" key={r.id}
                    className={`map-region-tab ${activeRegion === r.id ? 'on' : ''}`}
                    onClick={() => jumpToRegion(r.id)}>
              {REGIONS_STATIC[r.id]?.name || r.name}
            </button>
          ))}
        </div>
      )}
      {mapped.length > 3 && (
        <div className="map-region-tabs map-pin-filter">
          {PIN_FILTERS.map(f => (
            <button type="button" key={f.key}
                    className={`map-region-tab ${pinFilter === f.key ? 'on' : ''}`}
                    onClick={() => { haptic(); setPinFilter(f.key); }}>
              {f.label}
            </button>
          ))}
        </div>
      )}
      <div className="mapview-frame">
        <span className="map-frame-corner tl" /><span className="map-frame-corner tr" />
        <span className="map-frame-corner bl" /><span className="map-frame-corner br" />
        <ZoomPanMap ref={mapRef} onInteract={() => setPin(null)} onViewChange={setView}>
          <MapFrame region={{ castles: filteredCastles }} coords={coords} pin={pin}
                    onPinClick={(c) => { haptic(); setPin(pin === c.name ? null : c.name); }}
                    onSelectTarget={onSelectTarget} pickLabel={pickLabel}
                    colorMode={colorMode} routeSegments={routeSegments} seaLaneSegments={seaLaneSegments}
                    campaigns={(data.campaigns || []).filter(c => !c.arrived)} />
        </ZoomPanMap>
        {mapped.length > 6 && <MiniMap pins={mapped} view={view} onJump={jumpFromMiniMap} />}
        {myPin && (
          <button type="button" className="map-my-castle" onClick={jumpToMine} aria-label="پرش به قلعهٔ خودم">
            <Keep s={14} />
          </button>
        )}
      </div>
      {ownedRegions.length > 0 && (
        <div className="map-legend">
          {colorMode === 'region' ? ownedRegions.map(rid => (
            <span className="map-legend-item" key={rid}>
              <span className="map-legend-dot" style={{ background: REGION_COLORS[rid] }} />
              {REGIONS_STATIC[rid]?.name || rid}
            </span>
          )) : pactTypesPresent.map(t => (
            <span className="map-legend-item" key={t}>
              <span className="map-legend-dot" style={{ background: PACT_COLORS[t] }} />
              {t === 'none' ? 'بدون پیمان' : ALLIANCE_TYPES[t]?.name}
            </span>
          ))}
          <button type="button" className="map-legend-toggle"
                  onClick={() => { haptic(); setColorMode(m => m === 'region' ? 'pact' : 'region'); }}>
            رنگ‌بندی: {colorMode === 'region' ? 'اقلیم' : 'پیمان'}
          </button>
        </div>
      )}
    </div>
  );
}

