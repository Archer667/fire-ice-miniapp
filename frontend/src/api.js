import { getInitData } from './telegram.js';

const BASE = import.meta.env.VITE_API_URL || '';
export const MOCK = !BASE;

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'tma ' + getInitData(),
      ...(import.meta.env.DEV ? { 'X-Dev-User': '1:لرد آزمایشی' } : {}),
      ...opts.headers,
    },
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || 'خطای سرور');
  }
  return res.json();
}

/* ---------- دیتای mock برای حالت بدون سرور ---------- */
import { REGIONS_STATIC, BUILDINGS } from './gamedata.js';

const mockMe = { registered: false };
const mockConstruction = { buildings: {}, queue: null };
const M = {
  gamedata: { regions: REGIONS_STATIC },
  me: () => mockMe,
  register: (b) => {
    Object.assign(mockMe, {
      registered: true, name: b.name, region: b.region,
      region_name: REGIONS_STATIC[b.region].name, castle: b.castle,
      is_port: REGIONS_STATIC[b.region].ports.includes(b.castle),
      resources: { gold: 1000, food: 800, men: 500, iron: 100, stone: 100 },
      points: 100, rank: 5, total_players: 12, day: 18, season_length: 30,
    });
    return { ok: true };
  },
  map: () => ({
    regions: Object.entries(REGIONS_STATIC).map(([id, r]) => ({
      id, name: r.name,
      castles: [...r.castles.map(n => ({ name: n, owner: null, port: false })),
                ...r.ports.map(n => ({ name: n, owner: null, port: true }))],
    })),
    campaigns: [
      { from: 'کسترلی راک', to: 'ریورران', mine: false, revealed_minutes_ago: 23 },
      { from: 'پایک', to: 'وایت هاربر', mine: false, revealed_minutes_ago: 61 },
    ],
  }),
  leaderboard: () => [
    { rank: 1, name: 'دنریس تارگرین', castle: 'دراگون‌استون', region: 'کراون‌لندز', points: 2380 },
    { rank: 2, name: 'تایوین لنیستر', castle: 'کسترلی راک', region: 'وسترلندز', points: 2140 },
    { rank: 3, name: 'مارگری تایرل', castle: 'های‌گاردن', region: 'ریچ', points: 1990 },
    { rank: 4, name: mockMe.name || 'تو', castle: mockMe.castle || '—', region: mockMe.region_name || '—', points: 100, me: true },
  ],
  inbox: () => [
    { with_name: 'تایوین لنیستر', last_text: 'پیشنهاد پیمان عدم‌تجاوز — تا پایان زمستان.', last_at: '', unread: 1 },
    { with_name: 'مارگری تایرل', last_text: 'ریچ آمادهٔ فروش گندم است. ۲۰۰ واحد در برابر ۱۵۰ طلا؟', last_at: '', unread: 1 },
    { with_name: 'یارا گریجوی', last_text: 'آنچه مرده است هرگز نمی‌میرد.', last_at: '', unread: 0 },
  ],
  thread: () => [
    { mine: false, text: 'پیشنهاد پیمان عدم‌تجاوز — تا پایان زمستان. پاسخت را با همین کلاغ بفرست.' },
    { mine: true, text: 'شمال دربارهٔ پیشنهادت می‌اندیشد، لرد لنیستر.' },
  ],
  construction: () => ({ buildings: mockConstruction.buildings, queue: mockConstruction.queue, resources: mockMe.resources }),
  buildStart: (id) => {
    const b = BUILDINGS.find(x => x.id === id);
    Object.entries(b.cost).forEach(([k, v]) => { mockMe.resources[k] = (mockMe.resources[k] || 0) - v; });
    mockConstruction.queue = { building_id: id, finishes_at: new Date(Date.now() + b.hours * 3600 * 1000).toISOString() };
    return { buildings: mockConstruction.buildings, queue: mockConstruction.queue, resources: mockMe.resources };
  },
};

/* ---------- API عمومی ---------- */
export const api = {
  gamedata:  () => MOCK ? Promise.resolve(M.gamedata) : req('/api/gamedata'),
  me:        () => MOCK ? Promise.resolve(M.me()) : req('/api/players/me'),
  register:  (b) => MOCK ? Promise.resolve(M.register(b)) : req('/api/players/register', { method: 'POST', body: JSON.stringify(b) }),
  map:       () => MOCK ? Promise.resolve(M.map()) : req('/api/map'),
  submitWar: (b) => MOCK ? Promise.resolve({ ok: true }) : req('/api/war/submit', { method: 'POST', body: JSON.stringify(b) }),
  leaderboard: () => MOCK ? Promise.resolve(M.leaderboard()) : req('/api/leaderboard'),
  inbox:     () => MOCK ? Promise.resolve(M.inbox()) : req('/api/ravens/inbox'),
  thread:    (name) => MOCK ? Promise.resolve(M.thread()) : req('/api/ravens/thread/' + encodeURIComponent(name)),
  sendRaven: (b) => MOCK ? Promise.resolve({ ok: true }) : req('/api/ravens/send', { method: 'POST', body: JSON.stringify(b) }),
  construction: () => MOCK ? Promise.resolve(M.construction()) : req('/api/construction'),
  buildStart: (building_id) => MOCK ? Promise.resolve(M.buildStart(building_id)) : req('/api/construction/start', { method: 'POST', body: JSON.stringify({ building_id }) }),
};
