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
import { REGIONS_STATIC, BUILDINGS_STATIC, MAX_BUILDING_LEVEL, buildingCost, buildingHours } from './gamedata.js';

const mockMe = { registered: false };
const mockBuildings = {}; // building_id -> { level, upgrade_to, ready_at }

function mockResolve() {
  const now = Date.now();
  for (const st of Object.values(mockBuildings)) {
    if (st.upgrade_to && st.ready_at && new Date(st.ready_at).getTime() <= now) {
      st.level = st.upgrade_to; st.upgrade_to = null; st.ready_at = null;
    }
  }
}

function mockCanAfford(cost) {
  return Object.entries(cost).every(([k, v]) => (mockMe.resources?.[k] ?? 0) >= v);
}
function mockPay(cost) {
  for (const [k, v] of Object.entries(cost)) mockMe.resources[k] -= v;
}
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
  buildings: () => {
    mockResolve();
    return Object.entries(BUILDINGS_STATIC).map(([id, meta]) => {
      const st = mockBuildings[id] || { level: 0, upgrade_to: null, ready_at: null };
      const next = st.upgrade_to || (st.level < MAX_BUILDING_LEVEL ? st.level + 1 : null);
      return {
        id, name: meta.name, type: meta.type, unit: meta.unit,
        level: st.level, max_level: MAX_BUILDING_LEVEL,
        upgrading: !!st.upgrade_to, ready_at: st.ready_at,
        next_level: next,
        next_cost: next ? buildingCost(id, next) : null,
        next_hours: next ? buildingHours(id, next) : null,
      };
    });
  },
  buildAction: (id, requireBuilt) => {
    mockResolve();
    const st = mockBuildings[id] || { level: 0, upgrade_to: null, ready_at: null };
    if (st.upgrade_to) throw new Error('این ساختمان هم‌اکنون در حال ساخت است');
    if (requireBuilt && st.level === 0) throw new Error('اول این ساختمان را بنا کن');
    if (!requireBuilt && st.level > 0) throw new Error('این ساختمان قبلاً بنا شده — آن را ارتقا بده');
    if (st.level >= MAX_BUILDING_LEVEL) throw new Error('این ساختمان به بیشینهٔ سطح رسیده');
    const target = st.level + 1;
    const cost = buildingCost(id, target);
    if (!mockCanAfford(cost)) throw new Error('منابع کافی نیست');
    mockPay(cost);
    st.upgrade_to = target;
    st.ready_at = new Date(Date.now() + buildingHours(id, target) * 3600 * 1000).toISOString();
    mockBuildings[id] = st;
    return { ok: true, target_level: target, cost, ready_at: st.ready_at };
  },
};

/* ---------- API عمومی ---------- */
// در حالت MOCK نتیجه با Promise.resolve بسته‌بندی می‌شود تا امضای async با حالت واقعی یکی بماند
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
  buildings: () => MOCK ? Promise.resolve(M.buildings()) : req('/api/buildings'),
  buildBuilding:   (id) => MOCK ? Promise.resolve(M.buildAction(id, false)) : req('/api/buildings/build',   { method: 'POST', body: JSON.stringify({ building_id: id }) }),
  upgradeBuilding: (id) => MOCK ? Promise.resolve(M.buildAction(id, true))  : req('/api/buildings/upgrade', { method: 'POST', body: JSON.stringify({ building_id: id }) }),
};
