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
  COMMON_TROOPS, SPECIAL_COST, OP_TYPES, TROOP_UNIT_BUILDINGS, FOOD_COST_REGULAR, FOOD_COST_SPECIAL, travelMinutes,
  SPY_GOLD_COST, SPY_MEN_COST, spyTravelMinutes,
} from './gamedata.js';

const mockMe = { registered: false };
const mockBuildings = {}; // building_id -> { level, upgrade_to, ready_at }
const mockAlliances = []; // {id, mine_proposed, other_name, type, type_name, status}
let mockAllianceSeq = 1;
let mockLastFeast = null;
const mockCampaigns = []; // {id, origin_castle, op_type, target_castle, troops, gold_cost, men_committed, food_per_day, active, created_at, last_food_tick, travel_minutes, arrival_at}
let mockCampaignSeq = 1;
const mockMapCastles = []; // {region, name, port, x, y, custom}
const mockBattleReports = []; // {id, participants:[name], text, created_at}
let mockBattleSeq = 1;
const mockSpyMissions = []; // {id, target, travel_minutes, arrival_at, success, report, created_at}
let mockSpySeq = 1;

function mockResolveRegion(name) {
  for (const [rid, r] of Object.entries(REGIONS_STATIC)) {
    if (r.castles.includes(name) || r.ports.includes(name)) return rid;
  }
  const custom = mockMapCastles.find(m => m.name === name);
  return custom ? custom.region : null;
}
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

function mockResolveCampaigns() {
  if (!mockMe.resources) return;
  const nowMs = Date.now();
  for (const c of mockCampaigns) {
    if (!c.active) continue;
    const last = new Date(c.last_food_tick).getTime();
    const days = Math.floor((nowMs - last) / 86400000);
    if (days <= 0) continue;
    mockMe.resources.food = Math.max(0, (mockMe.resources.food ?? 0) - c.food_per_day * days);
    c.last_food_tick = new Date(last + days * 86400000).toISOString();
  }
}

function mockStationedOrigins() {
  return mockCampaigns.filter(c => c.active && c.op_type === 'garrison').map(c => c.target_castle);
}

function mockCanAfford(cost) {
  return Object.entries(cost).every(([k, v]) => (mockMe.resources?.[k] ?? 0) >= v);
}
function mockPay(cost) {
  for (const [k, v] of Object.entries(cost)) mockMe.resources[k] -= v;
}
const M = {
  gamedata: { regions: REGIONS_STATIC },
  me: () => {
    mockResolveCampaigns();
    if (mockMe.registered) mockMe.active_campaigns = mockCampaigns.filter(c => c.active).length;
    return mockMe;
  },
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
  map: () => {
    mockResolveCampaigns();
    const owners = {};
    for (const p of MOCK_PLAYERS) {
      owners[p.castle] = { tg_id: p.tg_id, name: p.name, title: p.title, points: 500 + p.tg_id % 500, overlord_name: null };
    }
    if (mockMe.registered) {
      owners[mockMe.castle] = { tg_id: 1, name: mockMe.name, title: mockMe.title, points: mockMe.points, overlord_name: null };
    }
    const nowMs = Date.now();
    return {
      regions: Object.entries(REGIONS_STATIC).map(([id, r]) => {
        const custom = mockMapCastles.filter(m => m.region === id && m.custom);
        const coords = {};
        for (const m of mockMapCastles.filter(m => m.region === id)) coords[m.name] = [m.x, m.y];
        return {
          id, name: r.name,
          castles: [
            ...r.castles.map(n => ({ name: n, owner: owners[n] || null, port: false })),
            ...r.ports.map(n => ({ name: n, owner: owners[n] || null, port: true })),
            ...custom.map(c => ({ name: c.name, owner: owners[c.name] || null, port: c.port })),
          ],
          coords,
        };
      }),
      campaigns: [
        { from: 'کسترلی راک', to: 'ریورران', op_type: 'attack', mine: false, revealed_minutes_ago: 23, travel_minutes: 45, arrived: true },
        { from: 'پایک', to: 'وایت هاربر', op_type: 'naval_raid', mine: false, revealed_minutes_ago: 61, travel_minutes: 65, arrived: false },
        ...mockCampaigns.filter(c => c.active).map(c => ({
          from: c.origin_castle, to: c.target_castle, op_type: c.op_type, mine: true,
          revealed_minutes_ago: Math.floor((nowMs - new Date(c.created_at).getTime()) / 60000),
          travel_minutes: c.travel_minutes, arrived: nowMs >= new Date(c.arrival_at).getTime(),
        })),
      ],
    };
  },
  adminMapOptions: (region) => {
    const r = REGIONS_STATIC[region];
    if (!r) return [];
    const placed = new Set(mockMapCastles.filter(m => m.region === region).map(m => m.name));
    return [
      ...r.castles.filter(n => !placed.has(n)).map(n => ({ name: n, port: false })),
      ...r.ports.filter(n => !placed.has(n)).map(n => ({ name: n, port: true })),
    ];
  },
  adminAddMapCastle: (body) => {
    const r = REGIONS_STATIC[body.region];
    if (!r) throw new Error('اقلیم نامعتبر');
    if (!(body.x >= 0 && body.x <= 100 && body.y >= 0 && body.y <= 100)) throw new Error('مختصات نامعتبر');
    const allNames = new Set(mockMapCastles.map(m => m.name));
    for (const reg of Object.values(REGIONS_STATIC)) { reg.castles.forEach(n => allNames.add(n)); reg.ports.forEach(n => allNames.add(n)); }

    let name, port, custom;
    if (body.new_name && body.new_name.trim()) {
      name = body.new_name.trim().slice(0, 40);
      if (allNames.has(name)) throw new Error('این اسم قبلاً در بازی وجود دارد');
      port = !!body.port; custom = true;
    } else {
      name = (body.name || '').trim();
      if (![...r.castles, ...r.ports].includes(name)) throw new Error('این قلعه/بندر در دیتای این اقلیم نیست');
      if (mockMapCastles.some(m => m.region === body.region && m.name === name)) throw new Error('این قلعه از قبل روی نقشه گذاشته شده');
      port = r.ports.includes(name); custom = false;
    }
    mockMapCastles.push({ region: body.region, name, port, x: body.x, y: body.y, custom });
    return { ok: true, name };
  },
  submitCampaign: (body) => {
    mockResolveCampaigns();
    const op = OP_TYPES.find(o => o.id === body.op_type);
    if (!op) throw new Error('نوع عملیات نامعتبر');

    const validOrigins = [mockMe.castle, ...mockStationedOrigins()];
    if (!validOrigins.includes(body.origin_castle)) {
      throw new Error('مبدا باید قلعهٔ خودت یا جایی باشد که لشکرت همین الان مستقر است');
    }

    let targetCastle = body.origin_castle;
    if (op.needsTarget) {
      if (!body.target_castle) throw new Error('مقصد را مشخص کن');
      targetCastle = body.target_castle;
      if (op.portOnly) {
        const isPort = Object.values(REGIONS_STATIC).some(r => r.ports.includes(targetCastle))
          || mockMapCastles.some(m => m.name === targetCastle && m.port);
        if (!isPort) throw new Error('غارت دریایی فقط علیه اهداف بندری ممکن است');
      }
      if (body.op_type !== 'garrison' && (body.plan || '').trim().length < 50) {
        throw new Error('سناریو خیلی کوتاه است — نقشه‌ات را شرح بده');
      }
    }

    const specials = REGIONS_STATIC[mockMe.region]?.special || [];
    let gold = 0, men = 0, food = 0;
    for (const [tid, n] of Object.entries(body.troops || {})) {
      if (!n || n <= 0) continue;
      const common = COMMON_TROOPS.find(t => t.id === tid);
      if (common) {
        const req = TROOP_UNIT_BUILDINGS[tid];
        if (req) {
          const campLevel = mockBuildings[req.camp]?.level || 0;
          const armoryLevel = mockBuildings[req.armory]?.level || 0;
          if (campLevel <= 0 || armoryLevel <= 0) {
            throw new Error(`برای گسیل ${common.name} باید ${BUILDINGS_STATIC[req.camp].name} و ${BUILDINGS_STATIC[req.armory].name} را ساخته باشی`);
          }
        }
        gold += common.cost * n;
        food += FOOD_COST_REGULAR * n;
      } else if (specials.includes(tid)) {
        gold += SPECIAL_COST * n;
        food += FOOD_COST_SPECIAL * n;
      } else {
        throw new Error(`نیروی نامعتبر: ${tid}`);
      }
      men += n;
    }
    if (men <= 0) throw new Error('هیچ نیرویی گسیل نکرده‌ای');
    if (!mockCanAfford({ gold })) throw new Error('خزانه کافی نیست');
    if ((mockMe.resources.men ?? 0) < men) throw new Error('نفرات کافی نداری');

    mockPay({ gold });
    mockMe.resources.men -= men;

    const sameCastle = targetCastle === body.origin_castle;
    const originRegion = mockResolveRegion(body.origin_castle) || mockMe.region;
    const targetRegion = sameCastle ? originRegion : (mockResolveRegion(targetCastle) || originRegion);
    const travel = travelMinutes(sameCastle, originRegion, targetRegion);

    const nowIso = new Date().toISOString();
    const doc = {
      id: String(mockCampaignSeq++),
      origin_castle: body.origin_castle, op_type: body.op_type, target_castle: targetCastle,
      plan: body.plan || '', troops: body.troops,
      gold_cost: gold, men_committed: men, food_per_day: food,
      active: true, created_at: nowIso, last_food_tick: nowIso,
      travel_minutes: travel, arrival_at: new Date(Date.now() + travel * 60000).toISOString(),
    };
    mockCampaigns.push(doc);
    return { ok: true, id: doc.id, gold_cost: gold, men_committed: men, food_per_day: food, travel_minutes: travel };
  },
  cancelCampaign: (id) => {
    const c = mockCampaigns.find(x => x.id === id);
    if (!c) throw new Error('لشکر پیدا نشد');
    if (!c.active) throw new Error('این لشکر دیگر فعال نیست');
    c.active = false;
    mockMe.resources.men = (mockMe.resources.men ?? 0) + c.men_committed;
    return { ok: true };
  },
  warMine: () => {
    mockResolveCampaigns();
    const nowMs = Date.now();
    return mockCampaigns.slice().reverse().map(c => ({
      id: c.id,
      op_type: c.op_type, op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
      origin: c.origin_castle, target: c.target_castle,
      active: c.active,
      gold_cost: c.gold_cost, men_committed: c.men_committed, food_per_day: c.food_per_day,
      days_active: Math.max(0, Math.floor((nowMs - new Date(c.created_at).getTime()) / 86400000)),
      travel_minutes: c.travel_minutes, arrived: nowMs >= new Date(c.arrival_at).getTime(),
      created_at: c.created_at,
    }));
  },
  adminCampaigns: () => {
    mockResolveCampaigns();
    const nowMs = Date.now();
    return mockCampaigns.slice().reverse().map(c => ({
      id: c.id, player: mockMe.name,
      from: c.origin_castle, to: c.target_castle,
      op_type: c.op_type, op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
      plan: c.plan,
      troops: Object.entries(c.troops || {}).filter(([, n]) => n > 0).map(([tid, n]) => ({
        name: COMMON_TROOPS.find(t => t.id === tid)?.name || tid, count: n,
      })),
      gold_cost: c.gold_cost, men_committed: c.men_committed, food_per_day: c.food_per_day,
      travel_minutes: c.travel_minutes, arrived: nowMs >= new Date(c.arrival_at).getTime(),
      active: c.active, created_at: c.created_at,
    }));
  },
  adminBattles: () => mockBattleReports.slice().reverse(),
  adminCreateBattleReport: (participantTgIds, text) => {
    if (!participantTgIds.length) throw new Error('حداقل یک شرکت‌کننده انتخاب کن');
    const t = (text || '').trim();
    if (!t) throw new Error('متن روایت خالی است');
    const names = participantTgIds.map(id => MOCK_PLAYERS.find(p => p.tg_id === id)?.name || String(id));
    mockBattleReports.push({ id: String(mockBattleSeq++), participants: names, text: t, created_at: new Date().toISOString() });
    return { ok: true, sent_to: names.length };
  },
  sendSpy: (targetCastle) => {
    mockResolveCampaigns();
    if (targetCastle === mockMe.castle) throw new Error('نمی‌توانی جاسوس به قلعهٔ خودت بفرستی');
    const targetPlayer = MOCK_PLAYERS.find(p => p.castle === targetCastle);
    if (!targetPlayer) throw new Error('این قلعه صاحبی ندارد که جاسوسی‌اش کنی');
    if (!mockCanAfford({ gold: SPY_GOLD_COST })) throw new Error('خزانه کافی نیست');
    if ((mockMe.resources.men ?? 0) < SPY_MEN_COST) throw new Error('نفرات کافی نداری');

    mockPay({ gold: SPY_GOLD_COST });
    mockMe.resources.men -= SPY_MEN_COST;

    const targetRegion = mockResolveRegion(targetCastle) || mockMe.region;
    const travel = spyTravelMinutes(mockMe.region, targetRegion);
    const success = Math.random() < 0.8;

    const report = success ? {
      resources: {
        gold: 400 + (targetPlayer.tg_id % 600), food: 300 + (targetPlayer.tg_id % 400),
        men: 200 + (targetPlayer.tg_id % 300), wood: 80, stone: 60, iron: 40, wine: 10,
      },
      military: [{ name: 'پادگان پیاده‌نظام', level: 2 }],
      defense: [{ name: 'برج نگهبانی', level: 1 }],
      campaigns: [],
    } : null;

    const nowIso = new Date().toISOString();
    mockSpyMissions.push({
      id: String(mockSpySeq++), target: targetCastle, travel_minutes: travel,
      arrival_at: new Date(Date.now() + travel * 60000).toISOString(),
      success, report, created_at: nowIso,
    });
    return { ok: true, travel_minutes: travel };
  },
  spyMine: () => {
    const nowMs = Date.now();
    return mockSpyMissions.slice().reverse().map(m => {
      const arrived = nowMs >= new Date(m.arrival_at).getTime();
      return {
        id: m.id, target: m.target, travel_minutes: m.travel_minutes,
        arrived, success: arrived ? m.success : null, report: (arrived && m.success) ? m.report : null,
        created_at: m.created_at,
      };
    });
  },
  leaderboard: () => [
    { rank: 1, name: 'دنریس تارگرین', castle: 'دراگون‌استون', region: 'کراون‌لندز', points: 2380 },
    { rank: 2, name: 'تایوین لنیستر', castle: 'کسترلی راک', region: 'وسترلندز', points: 2140 },
    { rank: 3, name: 'مارگری تایرل', castle: 'های‌گاردن', region: 'ریچ', points: 1990 },
    { rank: 4, name: mockMe.name || 'تو', castle: mockMe.castle || '—', region: mockMe.region_name || '—', points: 100, me: true },
  ],
  ravensUnread: () => ({ count: 0 }),
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
  // مقام‌ها/رای‌گیری در حالت mock پیاده نشده — این اپ دمو تک‌بازیکنه و پنل ادمین کامل به بک‌اند واقعی نیاز دارد
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
  warMine:   () => MOCK ? Promise.resolve(M.warMine()) : req('/api/war/mine'),
  submitCampaign: (b) => MOCK ? Promise.resolve(M.submitCampaign(b)) : req('/api/war/submit', { method: 'POST', body: JSON.stringify(b) }),
  cancelCampaign: (id) => MOCK ? Promise.resolve(M.cancelCampaign(id)) : req(`/api/war/${id}/cancel`, { method: 'POST' }),
  adminMapOptions: (region) => MOCK ? Promise.resolve(M.adminMapOptions(region)) : req('/api/admin/map/options?region=' + encodeURIComponent(region)),
  adminAddMapCastle: (b) => MOCK ? Promise.resolve(M.adminAddMapCastle(b)) : req('/api/admin/map/castles', { method: 'POST', body: JSON.stringify(b) }),
  leaderboard: () => MOCK ? Promise.resolve(M.leaderboard()) : req('/api/leaderboard'),
  ravensUnread: () => MOCK ? Promise.resolve(M.ravensUnread()) : req('/api/ravens/unread'),
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
  adminCampaigns: () => MOCK ? Promise.resolve(M.adminCampaigns()) : req('/api/admin/campaigns'),
  adminBattles: () => MOCK ? Promise.resolve(M.adminBattles()) : req('/api/admin/battles'),
  adminCreateBattleReport: (participantTgIds, text) => MOCK ? Promise.resolve(M.adminCreateBattleReport(participantTgIds, text))
    : req('/api/admin/battles', { method: 'POST', body: JSON.stringify({ participant_tg_ids: participantTgIds, text }) }),

  /* ---------- جاسوسی ---------- */
  sendSpy: (targetCastle) => MOCK ? Promise.resolve(M.sendSpy(targetCastle))
    : req('/api/espionage/send', { method: 'POST', body: JSON.stringify({ target_castle: targetCastle }) }),
  spyMine: () => MOCK ? Promise.resolve(M.spyMine()) : req('/api/espionage/mine'),

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
