const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' };
const I = ({ s = 21, className, children }) => <svg width={s} height={s} viewBox="0 0 24 24" className={className} {...p}>{children}</svg>;

export const Keep   = (o) => <I {...o}><path d="M5 21V10l2-2V5h2.2v2h1.6V5h2.4v2h1.6V5H17v3l2 2v11"/><path d="M9.8 21v-4.6a2.2 2.2 0 014.4 0V21"/></I>;
export const Map    = (o) => <I {...o}><path d="M9 20l-6-2V4l6 2 6-2 6 2v14l-6-2-6 2z"/><path d="M9 6v14M15 4v14"/></I>;
export const Swords = (o) => <I {...o}><path d="M4.5 4.5l15 15M19.5 4.5l-15 15M14 6.5l3.5 3.5M6.5 14l3.5 3.5"/></I>;
export const Crown  = (o) => <I {...o}><path d="M4 9l4 3.5L12 6l4 6.5L20 9l-1.6 9H5.6L4 9z"/></I>;
export const Mail   = (o) => <I {...o}><rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M3 8l9 5.5L21 8"/></I>;
export const Coin   = (o) => <I {...o}><circle cx="12" cy="12" r="8.2"/><path d="M12 7v10"/><path d="M15 9.4c0-1.3-1.3-2.2-3-2.2s-3 .8-3 2c0 1.2 1.2 1.6 3 2.1s3 .9 3 2.1c0 1.2-1.3 2.1-3 2.1s-3-.9-3-2.2"/></I>;
export const Wheat  = (o) => <I {...o}><path d="M12 3v18M12 7c-3 0-4.5-1.5-4.5-4 3 0 4.5 1.5 4.5 4zM12 7c3 0 4.5-1.5 4.5-4-3 0-4.5 1.5-4.5 4zM12 13c-3 0-5-1.5-5-4.5 3 0 5 1.7 5 4.5zM12 13c3 0 5-1.5 5-4.5-3 0-5 1.7-5 4.5z"/></I>;
export const People = (o) => <I {...o}><circle cx="9" cy="8" r="3.2"/><path d="M3.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/><circle cx="16.5" cy="9" r="2.6"/><path d="M15.5 15.2c2.8.2 5 2 5 4.8"/></I>;
export const Pick   = (o) => <I {...o}><path d="M7 16l1.3-6.5h7.4L17 16z"/><path d="M6 16h12"/></I>;
export const Rock   = (o) => <I {...o}><path d="M7 20l-3.5-5L8 8h5l4 4-2 8H7z"/><path d="M13 8l3-4 4.5 6-2.5 2"/></I>;
export const Build  = (o) => <I {...o}><path d="M3 21h18M6 21V8l6-4 6 4v13"/><path d="M10 21v-5h4v5"/></I>;
export const Shield = (o) => <I {...o}><path d="M12 3l7 4v5c0 4.4-3 8-7 9-4-1-7-4.6-7-9V7l7-4z"/></I>;
export const Eye    = (o) => <I {...o}><circle cx="12" cy="12" r="3"/><path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/></I>;
export const Heart  = (o) => <I {...o}><path d="M12 21s-7-4.6-9.5-9A5.4 5.4 0 0112 6.5 5.4 5.4 0 0121.5 12C19 16.4 12 21 12 21z"/></I>;
export const Send   = (o) => <I {...o}><path d="M21 3L10 14M21 3l-7 19-4-8-8-4 19-7z"/></I>;
export const Plus   = (o) => <I {...o}><path d="M12 5v14M5 12h14"/></I>;
export const Back   = (o) => <I {...o}><path d="M15 6l-6 6 6 6"/></I>;
export const Menu   = (o) => <I {...o}><path d="M4 6h16M4 12h16M4 18h16"/></I>;
export const Close  = (o) => <I {...o}><path d="M6 6l12 12M18 6L6 18"/></I>;
export const Hammer = (o) => <I {...o}><path d="M14.5 6.5l3 3-7.5 7.5H7v-3l7.5-7.5z"/><path d="M13 5l4.5-2 3.5 3.5-2 4.5"/><path d="M4.5 19.5l2.5-2.5"/></I>;
export const Wine   = (o) => <I {...o}><path d="M7 3h10l-1 6a4 4 0 01-8 0L7 3z"/><path d="M12 13v6M9 21h6"/></I>;
export const Scroll = (o) => <I {...o}><path d="M6 4h10a2 2 0 012 2v13a2 2 0 01-2 2H8a2 2 0 01-2-2V4z"/><path d="M6 4a2 2 0 00-2 2v2h2"/><path d="M9 9h6M9 13h6"/></I>;
export const Wood    = (o) => <I {...o}><rect x="4" y="5.5" width="16" height="3.4" rx="1.2"/><rect x="4" y="10.3" width="16" height="3.4" rx="1.2"/><rect x="4" y="15.1" width="16" height="3.4" rx="1.2"/></I>;
export const Ship    = (o) => <I {...o}><path d="M4 15h16l-2 5H6l-2-5z"/><path d="M12 15V4M12 4l4 3h-4"/><path d="M8 8v4M16 9v3"/></I>;
export const Cart    = (o) => <I {...o}><circle cx="9" cy="20" r="1.3"/><circle cx="17" cy="20" r="1.3"/><path d="M2.5 3h2.2l2.2 12.2a2 2 0 002 1.8h8.3a2 2 0 002-1.7L21 7.5H6"/></I>;

/* آیکن‌های تزئینیِ فصل‌ها — پس‌زمینهٔ کم‌رنگ سکشن قلمرو */
export const Blossom  = (o) => <I {...o}><path d="M4 20c4-6 8-10 16-16"/><circle cx="9" cy="15" r="1.6"/><circle cx="13" cy="10.5" r="1.6"/><circle cx="17" cy="6.5" r="1.6"/></I>;
export const SunIcon  = (o) => <I {...o}><circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></I>;
export const Leaf     = (o) => <I {...o}><path d="M12 3c4 2 7 6 7 10a7 7 0 01-14 0c0-4 3-8 7-10z"/><path d="M12 3v18M12 10c-2-1-3.5-1-5 0M12 14c2.5-1.2 4.5-1 6 .3"/></I>;
export const Snowflake = (o) => <I {...o}><path d="M12 2v20M2 12h20M4.5 4.5l15 15M19.5 4.5l-15 15"/></I>;
