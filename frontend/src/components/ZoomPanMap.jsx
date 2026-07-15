import { createContext, useRef, useState } from 'react';

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;
const STEP = 0.6;

// زوم فعلی نقشه — تا عناصری مثل پاپ‌آپ اطلاعات بتوانند اندازهٔ خودشان را
// برعکسِ این مقدار جبران کنند و با زوم نقشه بزرگ/کوچک نشوند
export const ZoomContext = createContext(1);

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const dist = (touches) => Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY);

export default function ZoomPanMap({ children, className = '', onInteract }) {
  const wrapRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const gesture = useRef(null);

  const clampPan = (z, p) => {
    const el = wrapRef.current;
    if (!el) return p;
    const maxX = (el.clientWidth * (z - 1)) / 2;
    const maxY = (el.clientHeight * (z - 1)) / 2;
    return { x: clamp(p.x, -maxX, maxX), y: clamp(p.y, -maxY, maxY) };
  };

  // زوم/جابه‌جایی نقشه یعنی هر پاپ‌آپ بازی که کنار یک پین چسبیده دیگر معنی ندارد
  // (ممکن است پین از دید بیرون رفته باشد) — پس والد فرصت می‌گیرد آن را ببندد
  const applyZoom = (nextZoom) => {
    const z = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);
    setZoom(z);
    setPan(p => clampPan(z, p));
    onInteract?.();
  };

  const zoomIn = () => applyZoom(zoom + STEP);
  const zoomOut = () => applyZoom(zoom - STEP);
  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const onWheel = (e) => {
    e.preventDefault();
    applyZoom(zoom + (e.deltaY < 0 ? STEP / 2 : -STEP / 2));
  };

  const onTouchStart = (e) => {
    if (e.touches.length === 2) {
      gesture.current = { mode: 'pinch', startDist: dist(e.touches), startZoom: zoom };
    } else if (e.touches.length === 1) {
      gesture.current = {
        mode: 'pan', startX: e.touches[0].clientX, startY: e.touches[0].clientY,
        startPan: pan, moved: false,
      };
    }
  };

  const onTouchMove = (e) => {
    const g = gesture.current;
    if (!g) return;
    if (g.mode === 'pinch' && e.touches.length === 2) {
      e.preventDefault();
      applyZoom(g.startZoom * (dist(e.touches) / g.startDist));
    } else if (g.mode === 'pan' && e.touches.length === 1) {
      const dx = e.touches[0].clientX - g.startX;
      const dy = e.touches[0].clientY - g.startY;
      const justStartedMoving = !g.moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4);
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) g.moved = true;
      if (zoom > 1 && g.moved) {
        e.preventDefault();
        setPan(clampPan(zoom, { x: g.startPan.x + dx, y: g.startPan.y + dy }));
        if (justStartedMoving) onInteract?.();
      }
    }
  };

  const onTouchEnd = () => { gesture.current = null; };

  const mouseDrag = useRef(null);
  const onMouseDown = (e) => {
    if (zoom <= 1) return;
    mouseDrag.current = { startX: e.clientX, startY: e.clientY, startPan: pan, moved: false };
  };
  const onMouseMove = (e) => {
    if (!mouseDrag.current || e.buttons !== 1) return;
    const d = mouseDrag.current;
    if (!d.moved) { d.moved = true; onInteract?.(); }
    setPan(clampPan(zoom, { x: d.startPan.x + (e.clientX - d.startX), y: d.startPan.y + (e.clientY - d.startY) }));
  };
  const onMouseUp = () => { mouseDrag.current = null; };

  return (
    <div className={`zoommap ${className}`}>
      <div ref={wrapRef} className="zoommap-wrap"
           onWheel={onWheel}
           onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}
           onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
        <div className="zoommap-inner" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
          <ZoomContext.Provider value={zoom}>{children}</ZoomContext.Provider>
        </div>
      </div>
      <div className="zoommap-controls">
        <button type="button" onClick={zoomIn} aria-label="بزرگ‌نمایی">+</button>
        <button type="button" onClick={zoomOut} aria-label="کوچک‌نمایی">−</button>
        {zoom > 1 && <button type="button" onClick={reset} aria-label="بازنشانی زوم">⟲</button>}
      </div>
    </div>
  );
}
