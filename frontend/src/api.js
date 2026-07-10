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
import {
  REGIONS_STATIC, BUILDINGS_STATIC, MAX_BUILDING_LEVEL, buildingCost, buildingHours,
  DEFAULT_TITLE, POPULARITY_START, POPULARITY_MAX, TAX_RATE_DEFAULT, maxTaxRate,
  FEAST_COST, FEAST_POPULARITY_GAIN, ALLIANCE_TYPES, WARDEN_GROUPS,
} from './gamedata.js';

const mockMe = { registered: false };
const mockBuildings = {}; // building_id -> { level, upgrade_to, ready_at }
const mockAlliances = []; // {id, mine_proposed, other_name, type, type_name, status}
let mockAllianceSeq = 1;
let mockLastFeast = null;
const mockPolls = [
  { id: 'p1', question: 'بالادستی ریچ چه کسی باشد؟', options: ['مارگری تایرل', 'راندیل تارلی'],
    status: 'open', tally: [3, 1], total_votes: 4, eligible: true, my_vote: null },
];
const MOCK_PLAYERS = [
  { tg_id: 9001, name: 'دنریس تارگرین', castle: 'دراگون‌استون', region_name: 'کراون‌لندز', title: 'ملکه' },
  { tg_id: 9002, name: 'تایوین لنیستر', castle: 'کسترلی راک', region_name: 'وسترلندز', title: 'لرد' },
  { tg_id: 9003, name: 'مارگری تایرل', castle: 'های‌گاردن', region_name: 'ریچ', title: 'لیدی' },
  { tg_id: 9004, name: 'یارا گریجوی', castle: 'پایک', region_name: 'جزایر آهن', title: 'لیدی' },
  { tg_id: 9005, name: 'ادموری تالی', castle: 'ریورران', region_name: 'ریورلندز', title: 'لرد' },
];

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
      gender: b.gender, title: DEFAULT_TITLE[b.gender], rank_label: null,
      admin_role: 'full', // حالت mock تک‌بازیکنه — پنل ادمین همیشه برای تست محلی در دسترسه
      resources: { gold: 1000, food: 800, men: 500, iron: 100, stone: 100, wood: 150, wine: 0 },
      points: 100, alliance_count: 0, popularity: POPULARITY_START, tax_rate: TAX_RATE_DEFAULT,
      max_tax_rate: maxTaxRate(POPULARITY_START),
      rank: 5, total_players: 12, day: 18, season_length: 30,
    });
    return { ok: true };
  },
  setTax: (rate) => {
    const cap = maxTaxRate(mockMe.popularity ?? POPULARITY_START);
    if (rate < 0 || rate > cap) throw new Error(`نرخ مالیات باید بین ۰ تا ${cap} درصد باشد`);
    mockMe.tax_rate = rate;
    return { ok: true, tax_rate: rate };
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
    { with_tg_id: 9002, with_name: 'تایوین لنیستر', last_text: 'پیشنهاد پیمان عدم‌تجاوز — تا پایان زمستان.', last_at: '', unread: 1 },
    { with_tg_id: 9003, with_name: 'مارگری تایرل', last_text: 'ریچ آمادهٔ فروش گندم است. ۲۰۰ واحد در برابر ۱۵۰ طلا؟', last_at: '', unread: 1 },
    { with_tg_id: 9004, with_name: 'یارا گریجوی', last_text: 'آنچه مرده است هرگز نمی‌میرد.', last_at: '', unread: 0 },
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
        id, name: meta.name, type: meta.type, unit: meta.unit, requires_port: !!meta.requires_port,
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
    if (!requireBuilt && BUILDINGS_STATIC[id]?.requires_port && !mockMe.is_port) {
      throw new Error('این ساختمان فقط در قلعه/شهرهای دریایی و بندری ساخته می‌شود');
    }
    const target = st.level + 1;
    const cost = buildingCost(id, target);
    if (!mockCanAfford(cost)) throw new Error('منابع کافی نیست');
    mockPay(cost);
    st.upgrade_to = target;
    st.ready_at = new Date(Date.now() + buildingHours(id, target) * 3600 * 1000).toISOString();
    mockBuildings[id] = st;
    return { ok: true, target_level: target, cost, ready_at: st.ready_at };
  },
  titles: () => ({
    overlords: Object.fromEntries(Object.keys(REGIONS_STATIC).map(id => [id, null])),
    warden_groups: WARDEN_GROUPS,
    wardens: { south: null, central: null, north: null },
    king: null,
  }),
  diplomacyMine: () => mockAlliances,
  diplomacyPropose: (toTgIds, type) => {
    if (!ALLIANCE_TYPES[type]) throw new Error('نوع پیمان نامعتبر');
    if (!toTgIds.length) throw new Error('هیچ گیرنده‌ای انتخاب نشده');
    const cost = ALLIANCE_TYPES[type].wine_cost * toTgIds.length;
    if (!mockCanAfford({ wine: cost })) throw new Error(`شراب کافی برای پیشنهاد به ${toTgIds.length} نفر نداری`);
    mockPay({ wine: cost });
    for (const tgId of toTgIds) {
      const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
      mockAlliances.unshift({
        id: String(mockAllianceSeq++), mine_proposed: true, other_name: p ? p.name : String(tgId),
        type, type_name: ALLIANCE_TYPES[type].name, status: 'pending',
      });
    }
    return { ok: true, sent_to: toTgIds.length };
  },
  diplomacyRespond: (id, accept) => {
    const a = mockAlliances.find(x => x.id === id);
    if (!a) throw new Error('پیمان پیدا نشد');
    a.status = accept ? 'accepted' : 'rejected';
    if (accept) mockMe.alliance_count = (mockMe.alliance_count ?? 0) + 1;
    return { ok: true };
  },
  feast: () => {
    const now = Date.now();
    if (mockLastFeast && now - mockLastFeast < 24 * 3600 * 1000) {
      throw new Error('ضیافت را همین امروز برگزار کرده‌ای — فردا دوباره امتحان کن');
    }
    if (!mockCanAfford(FEAST_COST)) throw new Error('شراب یا غذای کافی برای ضیافت نداری');
    mockPay(FEAST_COST);
    mockMe.popularity = Math.min(POPULARITY_MAX, (mockMe.popularity ?? POPULARITY_START) + FEAST_POPULARITY_GAIN);
    mockMe.max_tax_rate = maxTaxRate(mockMe.popularity);
    mockLastFeast = now;
    return { ok: true, popularity: mockMe.popularity };
  },
  regionLeaderboard: () => {
    const rows = Object.entries(REGIONS_STATIC).map(([id, r]) => ({
      region: id, name: r.name,
      total_score: id === mockMe.region ? (mockMe.points ?? 100) : Math.round(Math.random() * 400),
      lord_count: id === mockMe.region ? 1 : Math.round(2 + Math.random() * 4),
      mine: id === mockMe.region,
    }));
    rows.sort((a, b) => b.total_score - a.total_score);
    return rows.map((r, i) => ({ ...r, rank: i + 1 }));
  },
  polls: () => mockPolls,
  vote: (id, option) => {
    const p = mockPolls.find(x => x.id === id);
    if (!p) throw new Error('رای‌گیری پیدا نشد');
    if (p.status !== 'open') throw new Error('این رای‌گیری بسته شده');
    if (p.my_vote !== null && p.my_vote !== undefined) p.tally[p.my_vote]--;
    else p.total_votes++;
    p.tally[option]++;
    p.my_vote = option;
    return { ...p };
  },
  searchPlayers: (q) => {
    if (q.trim().length < 2) return [];
    const needle = q.trim().toLowerCase();
    return MOCK_PLAYERS.filter(p => p.name.toLowerCase().includes(needle) || p.castle.toLowerCase().includes(needle));
  },
  sendRaven: (toTgIds, text) => {
    if (!toTgIds.length) throw new Error('هیچ گیرنده‌ای انتخاب نشده');
    if (!text.trim()) throw new Error('نامه خالی است');
    return { ok: true, sent_to: toTgIds.length };
  },
  // ادمین در حالت mock پیاده نشده — این اپ دمو تک‌بازیکنه و پنل ادمین به بک‌اند واقعی نیاز دارد
  adminPending: () => [],
  adminVerdict: () => ({ ok: true }),
  adminSetOverlord: () => ({ ok: true }),
  adminSetWarden: () => ({ ok: true }),
  adminSetKing: () => ({ ok: true }),
  adminSetEpithet: () => ({ ok: true }),
  adminCreatePoll: () => ({ ok: true }),
  adminClosePoll: () => ({ ok: true }),
  adminListAdmins: () => [],
  adminAddAdmin: () => ({ ok: true }),
  adminRemoveAdmin: () => ({ ok: true }),
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
  sendRaven: (toTgIds, text) => MOCK ? Promise.resolve(M.sendRaven(toTgIds, text))
    : req('/api/ravens/send', { method: 'POST', body: JSON.stringify({ to_tg_ids: toTgIds, text }) }),
  buildings: () => MOCK ? Promise.resolve(M.buildings()) : req('/api/buildings'),
  buildBuilding:   (id) => MOCK ? Promise.resolve(M.buildAction(id, false)) : req('/api/buildings/build',   { method: 'POST', body: JSON.stringify({ building_id: id }) }),
  upgradeBuilding: (id) => MOCK ? Promise.resolve(M.buildAction(id, true))  : req('/api/buildings/upgrade', { method: 'POST', body: JSON.stringify({ building_id: id }) }),
  setTax:    (rate) => MOCK ? Promise.resolve(M.setTax(rate)) : req('/api/players/tax', { method: 'POST', body: JSON.stringify({ rate }) }),
  titles:    () => MOCK ? Promise.resolve(M.titles()) : req('/api/titles'),
  diplomacyMine: () => MOCK ? Promise.resolve(M.diplomacyMine()) : req('/api/diplomacy/mine'),
  diplomacyPropose: (toTgIds, type) => MOCK ? Promise.resolve(M.diplomacyPropose(toTgIds, type))
    : req('/api/diplomacy/propose', { method: 'POST', body: JSON.stringify({ to_tg_ids: toTgIds, type }) }),
  diplomacyRespond: (id, accept) => MOCK ? Promise.resolve(M.diplomacyRespond(id, accept))
    : req(`/api/diplomacy/${id}/respond`, { method: 'POST', body: JSON.stringify({ accept }) }),
  feast: () => MOCK ? Promise.resolve(M.feast()) : req('/api/diplomacy/feast', { method: 'POST' }),
  regionLeaderboard: () => MOCK ? Promise.resolve(M.regionLeaderboard()) : req('/api/leaderboard/regions'),
  polls: () => MOCK ? Promise.resolve(M.polls()) : req('/api/polls'),
  vote:  (id, option) => MOCK ? Promise.resolve(M.vote(id, option)) : req(`/api/polls/${id}/vote`, { method: 'POST', body: JSON.stringify({ option }) }),
  searchPlayers: (q) => MOCK ? Promise.resolve(M.searchPlayers(q)) : req('/api/players/search?q=' + encodeURIComponent(q)),

  /* ---------- پنل ادمین ---------- */
  adminPending: () => MOCK ? Promise.resolve(M.adminPending()) : req('/api/admin/pending'),
  adminVerdict: (id, action, verdict, pointsDelta) => MOCK ? Promise.resolve(M.adminVerdict())
    : req(`/api/admin/${id}/${action}`, { method: 'POST', body: JSON.stringify({ verdict, points_delta: pointsDelta || 0 }) }),
  adminSetOverlord: (region, tgId) => MOCK ? Promise.resolve(M.adminSetOverlord())
    : req('/api/titles/overlord', { method: 'POST', body: JSON.stringify({ region, tg_id: tgId }) }),
  adminSetWarden: (group, tgId) => MOCK ? Promise.resolve(M.adminSetWarden())
    : req('/api/titles/warden', { method: 'POST', body: JSON.stringify({ group, tg_id: tgId }) }),
  adminSetKing: (tgId) => MOCK ? Promise.resolve(M.adminSetKing())
    : req('/api/titles/king', { method: 'POST', body: JSON.stringify({ tg_id: tgId }) }),
  adminSetEpithet: (tgId, title) => MOCK ? Promise.resolve(M.adminSetEpithet())
    : req('/api/titles/epithet', { method: 'POST', body: JSON.stringify({ tg_id: tgId, title }) }),
  adminCreatePoll: (question, options, eligibleTgIds) => MOCK ? Promise.resolve(M.adminCreatePoll())
    : req('/api/polls/admin/create', { method: 'POST', body: JSON.stringify({ question, options, eligible_tg_ids: eligibleTgIds }) }),
  adminClosePoll: (id) => MOCK ? Promise.resolve(M.adminClosePoll()) : req(`/api/polls/admin/${id}/close`, { method: 'POST' }),
  adminListAdmins: () => MOCK ? Promise.resolve(M.adminListAdmins()) : req('/api/admin/admins'),
  adminAddAdmin: (tgId) => MOCK ? Promise.resolve(M.adminAddAdmin())
    : req('/api/admin/admins', { method: 'POST', body: JSON.stringify({ tg_id: tgId }) }),
  adminRemoveAdmin: (tgId) => MOCK ? Promise.resolve(M.adminRemoveAdmin())
    : req(`/api/admin/admins/${tgId}`, { method: 'DELETE' }),
};
