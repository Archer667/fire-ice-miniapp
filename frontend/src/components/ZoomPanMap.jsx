import { createContext, forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';

const MAX_ZOOM = 4;
const STEP = 0.6;
const FLY_MS = 560; // باید با مدت transition کلاس .flying تو index.css یکی باشه

// زوم فعلی نقشه — تا عناصری مثل پاپ‌آپ اطلاعات بتوانند اندازهٔ خودشان را
// برعکسِ این مقدار جبران کنند و با زوم نقشه بزرگ/کوچک نشوند
export const ZoomContext = createContext(1);

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const dist = (touches) => Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY);

/** قابِ نقشه یه پنجرهٔ فشرده و ثابت‌اندازه‌ست، ولی خودِ تصویر (محتوا) به‌خاطر
 * نسبت طول‌به‌عرضش می‌تونه خیلی بلندتر از این پنجره باشه — پس همه‌جا باید بینِ
 * اندازهٔ «دیدگاه» (viewport = خودِ wrap) و اندازهٔ «محتوا» (content = zoommap-inner،
 * که هیچ‌وقت توسط overflow:hidden برش نمی‌خوره) فرق گذاشت */
function measure(wrapEl, contentEl) {
  const vW = wrapEl?.clientWidth || 0, vH = wrapEl?.clientHeight || 0;
  const cW = contentEl?.clientWidth || 0, cH = contentEl?.clientHeight || 0;
  return { vW, vH, cW, cH };
}

// بازهٔ مجازِ pan روی یک محور: اگه محتوا (با این زوم) از دیدگاه بزرگ‌تره، pan طوری
// محدود می‌شه که همیشه کاملاً دیدگاه رو بپوشونه؛ وگرنه (محتوا کوچیک‌تره) وسط‌چین می‌مونه
function clampAxis(p, contentSize, viewSize, z) {
  if (contentSize * z <= viewSize) return 0;
  const minP = viewSize - (contentSize * (1 + z)) / 2;
  const maxP = (contentSize * (z - 1)) / 2;
  return clamp(p, minP, maxP);
}

/** ref imperative: flyTo({x,y,w,h}) یه محدوده (درصدِ عرض/ارتفاعِ کاملِ تصویر) رو
 * وسطِ دید می‌آره و تا حدِ امکان زوم می‌کنه که کاملاً جا بشه؛ flyToPoint(x,y,zoom)
 * فقط رویِ یه نقطهٔ مشخص با زومِ دلخواه سنتر می‌کنه (برای «قلعهٔ خودم»/مینی‌مپ) */
const ZoomPanMap = forwardRef(function ZoomPanMap({ children, className = '', onInteract, onViewChange }, ref) {
  const wrapRef = useRef(null);
  const contentRef = useRef(null);
  const [minZoom, setMinZoom] = useState(1); // زومی که کلِ محتوا رو توی قابِ فشرده جا می‌ده (fit-all)
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [flying, setFlying] = useState(false);
  const gesture = useRef(null);
  const flyTimer = useRef(null);
  const fittedOnce = useRef(false);

  // تصویر نقشه ممکنه در WebView تلگرام بعد از mount رمزگشایی بشه. در آن حالت
  // اندازه‌گیریِ یک‌باره ارتفاع صفر می‌دید و نقشه تا رفرش بعدی ناپدید می‌ماند.
  const fitToViewport = useCallback(() => {
    const { vW, vH, cW, cH } = measure(wrapRef.current, contentRef.current);
    if (!vW || !vH || !cW || !cH) return;
    const fz = clamp(Math.min(vW / cW, vH / cH), 0.1, 1);
    setMinZoom(fz);
    if (!fittedOnce.current) {
      fittedOnce.current = true;
      setZoom(fz);
      setPan({ x: 0, y: 0 });
    }
  }, []);

  // پس از لود تصویر و هر تغییر اندازهٔ واقعی دوباره محاسبه می‌شود.
  useEffect(() => {
    fitToViewport();
    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(fitToViewport)
      : null;
    if (wrapRef.current) observer?.observe(wrapRef.current);
    if (contentRef.current) observer?.observe(contentRef.current);
    const image = contentRef.current?.querySelector('img');
    image?.addEventListener('load', fitToViewport);
    if (image?.complete) fitToViewport();
    window.addEventListener('resize', fitToViewport);
    return () => {
      observer?.disconnect();
      image?.removeEventListener('load', fitToViewport);
      window.removeEventListener('resize', fitToViewport);
    };
  }, [fitToViewport]);

  // به والد اطلاع می‌ده الان دقیقاً کدوم محدودهٔ درصدیِ تصویر تو دیده — برای مینی‌مپ
  useEffect(() => {
    if (!onViewChange) return;
    const { vW, vH, cW, cH } = measure(wrapRef.current, contentRef.current);
    if (!vW || !vH || !cW || !cH) return;
    const wPct = (vW / zoom / cW) * 100;
    const hPct = (vH / zoom / cH) * 100;
    const cxPct = 50 - (pan.x / zoom / cW) * 100;
    const cyPct = 50 - (pan.y / zoom / cH) * 100;
    onViewChange({ x: cxPct - wPct / 2, y: cyPct - hPct / 2, w: wPct, h: hPct });
  }, [zoom, pan, onViewChange]);

  const clampPan = (z, p) => {
    const { vW, vH, cW, cH } = measure(wrapRef.current, contentRef.current);
    if (!vW || !vH || !cW || !cH) return p;
    return { x: clampAxis(p.x, cW, vW, z), y: clampAxis(p.y, cH, vH, z) };
  };

  // زوم/جابه‌جایی نقشه یعنی هر پاپ‌آپ بازی که کنار یک پین چسبیده دیگر معنی ندارد
  // (ممکن است پین از دید بیرون رفته باشد) — پس والد فرصت می‌گیرد آن را ببندد
  const applyZoom = (nextZoom) => {
    const z = clamp(nextZoom, minZoom, MAX_ZOOM);
    setZoom(z);
    setPan(p => clampPan(z, p));
    onInteract?.();
  };

  const zoomIn = () => applyZoom(zoom + STEP);
  const zoomOut = () => applyZoom(zoom - STEP);
  const reset = () => { setFlying(true); setZoom(minZoom); setPan({ x: 0, y: 0 }); armFlyReset(); };

  const armFlyReset = () => {
    if (flyTimer.current) clearTimeout(flyTimer.current);
    flyTimer.current = setTimeout(() => setFlying(false), FLY_MS);
  };

  const flyToPoint = (xPct, yPct, targetZoom = 2.2) => {
    const { vW, vH, cW, cH } = measure(wrapRef.current, contentRef.current);
    if (!vW || !vH || !cW || !cH) return;
    const z = clamp(targetZoom, minZoom, MAX_ZOOM);
    const fx = xPct / 100, fy = yPct / 100;
    const rawX = (vW - cW) / 2 + z * cW * (0.5 - fx);
    const rawY = (vH - cH) / 2 + z * cH * (0.5 - fy);
    const p = clampPan(z, { x: rawX, y: rawY });
    setFlying(true);
    setZoom(z);
    setPan(p);
    onInteract?.();
    armFlyReset();
  };

  const flyToBox = ({ x, y, w, h }, pad = 1.18) => {
    const { vW, vH, cW, cH } = measure(wrapRef.current, contentRef.current);
    if (!vW || !vH || !cW || !cH) return;
    const fw = Math.max(w / 100, 0.02), fh = Math.max(h / 100, 0.02);
    const z = clamp(Math.min(vW / (fw * cW), vH / (fh * cH)) / pad, minZoom, MAX_ZOOM);
    flyToPoint(x + w / 2, y + h / 2, z);
  };

  useImperativeHandle(ref, () => ({ flyToPoint, flyToBox, reset, zoomIn, zoomOut }));

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
      if (zoom > minZoom && g.moved) {
        e.preventDefault();
        setPan(clampPan(zoom, { x: g.startPan.x + dx, y: g.startPan.y + dy }));
        if (justStartedMoving) onInteract?.();
      }
    }
  };

  const onTouchEnd = () => { gesture.current = null; };

  const mouseDrag = useRef(null);
  const onMouseDown = (e) => {
    if (zoom <= minZoom) return;
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
        <div ref={contentRef} className={`zoommap-inner ${flying ? 'flying' : ''}`} style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
          <ZoomContext.Provider value={zoom}>{children}</ZoomContext.Provider>
        </div>
      </div>
      <div className="zoommap-controls">
        <button type="button" onClick={zoomIn} aria-label="بزرگ‌نمایی">+</button>
        <button type="button" onClick={zoomOut} aria-label="کوچک‌نمایی">−</button>
        {zoom > minZoom + 0.01 && <button type="button" onClick={reset} aria-label="بازنشانی زوم">⟲</button>}
      </div>
    </div>
  );
});

export default ZoomPanMap;
