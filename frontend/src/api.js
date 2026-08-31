import { getInitData } from './telegram.js';

// در production نبودن VITE_API_URL یعنی API از همان origin و از مسیر /api
// سرو می‌شود (مثلاً rewrite ورسل). حالت mock فقط باید صریحاً فعال شود؛ وگرنه
// دیپلوی same-origin ناخواسته وارد دیتای نمایشی می‌شد.
// همهٔ دیپلوی‌های production، چه Vercel و چه VPS، API را از همان origin و
// مسیر /api می‌خوانند. این کار مانع می‌شود یک Environment Variable قدیمی
// (مثلاً آدرس Railway) داخل bundle باقی بماند و احراز هویت را دور بزند.
const BASE = import.meta.env.PROD ? '' : (import.meta.env.VITE_API_URL || '');
export const MOCK = import.meta.env.VITE_MOCK === 'true' || (import.meta.env.DEV && !BASE);

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
  DEFAULT_TITLE, POPULARITY_START, POPULARITY_MAX, TAX_RATE_DEFAULT,
  FEAST_COST, FEAST_POPULARITY_GAIN, ALLIANCE_TYPES, PRIVATE_ALLIANCE_MULTIPLIER, PACT_PRIORITY, WARDEN_GROUPS,
  COMMON_TROOPS, SPECIAL_COST, SPECIAL_POWER, CAMP_POWER_STEP, OP_TYPES, TROOP_UNIT_BUILDINGS, FOOD_COST_REGULAR, FOOD_COST_SPECIAL, travelMinutes, travelRoutes, pathUsesSea, DEFAULT_SEA_CASTLES,
  SPY_GOLD_COST, SPY_MEN_COST, spyTravelMinutes, TRADE_GOODS, TRADE_GOOD_NAMES, SMALL_COUNCIL_SEATS,
  ROLEPLAY_CATEGORIES, ATTACK_OP_TYPES, DEFENSE_OP_TYPES, ROLEPLAY_WINDOW_HOURS,
  campaignPower, REPORT_VISIBLE_HOURS, NAVAL_TROOPS, NAVAL_TROOP_IDS, NAVAL_CAMP_BUILDING,
  ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, buildingYield, buildingProduces, buildingCapBonus, BUILDING_OVERRIDES,
  RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE, RUMOR_COOLDOWN_HOURS, DAILY_REWARDS,
  WEAPON_NAMES, WEAPON_PER_SOLDIER, CASTLE_HOUSES, MAP_TERRAINS, SIEGE_EQUIPMENT,
  DAILY_PRODUCTION, RESOURCE_CAPS, taxYieldMultiplier,
} from './gamedata.js';

const mockMe = { registered: false };
const mockDaily = { streak: 0, lastClaimDate: null };

// صندوق کلاغ‌ها — قبلاً inbox() یه آرایهٔ ثابت نمایشی بود که هیچ‌وقت با اکشن‌های
// واقعی به‌روز نمی‌شد (برای همین نتیجهٔ جاسوسی/رول/... تو حالت آزمایشی هیچ‌جا دیده نمی‌شد)
const SYSTEM_SENDER_NAME = 'رخدادها';
const mockMessages = [ // {from_id, to_id, from_name, to_name, text, read, created_at} — دموی اولیه، هر اکشن واقعی هم بهش اضافه می‌شود
  { from_id: 0, to_id: 1, from_name: SYSTEM_SENDER_NAME, to_name: 'تو', text: 'لشکرت از وینترفل به ریوران رسید.', read: false, created_at: new Date(Date.now() - 3600000).toISOString() },
  { from_id: 9002, to_id: 1, from_name: 'تایوین لنیستر', to_name: 'تو', text: 'پیشنهاد پیمان عدم‌تجاوز — تا پایان زمستان. پاسخت را با همین کلاغ بفرست.', read: false, created_at: new Date(Date.now() - 7200000).toISOString() },
  { from_id: 1, to_id: 9002, from_name: 'تو', to_name: 'تایوین لنیستر', text: 'شمال دربارهٔ پیشنهادت می‌اندیشد، لرد لنیستر.', read: true, created_at: new Date(Date.now() - 7100000).toISOString() },
  { from_id: 9003, to_id: 1, from_name: 'مارگری تایرل', to_name: 'تو', text: 'ریچ آمادهٔ فروش گندم است. ۲۰۰ واحد در برابر ۱۵۰ طلا؟', read: false, created_at: new Date(Date.now() - 10800000).toISOString() },
  { from_id: 9004, to_id: 1, from_name: 'یارا گریجوی', to_name: 'تو', text: 'آنچه مرده است هرگز نمی‌میرد.', read: true, created_at: new Date(Date.now() - 14400000).toISOString() },
];
function mockSendSystemMessage(text) {
  mockMessages.push({
    from_id: 0, to_id: 1, from_name: SYSTEM_SENDER_NAME, to_name: mockMe.name || 'تو',
    text, read: false, created_at: new Date().toISOString(),
  });
}

function dailyTodayStr() { return new Date().toISOString().slice(0, 10); }
function dailyYesterdayStr() { const d = new Date(); d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10); }
function dailyPendingStreak() {
  const today = dailyTodayStr();
  if (mockDaily.lastClaimDate === today) return { streak: mockDaily.streak, claimedToday: true };
  if (mockDaily.lastClaimDate === dailyYesterdayStr()) return { streak: mockDaily.streak + 1, claimedToday: false };
  return { streak: 1, claimedToday: false };
}
function dailyDayInCycle(streak) { return ((streak - 1) % DAILY_REWARDS.length) + 1; }
const mockHierarchy = {
  king_tg_id: 1, small_council: {}, overlords: {}, wardens: { south: null, central: null, north: null },
  treasury_gold: 0, council_salary_rates: {}, king_salary_rate: 0,
}; // تک‌بازیکنه: خودت همیشه پادشاهی؛ overlords/wardens رو هیچ‌جای mock واقعاً پر نمی‌کنه
   // (adminSetOverlord/Warden هم no-op هستن)، پس نقشِ خراج‌گیریِ خودت همیشه None می‌مونه —
   // این یعنی جریانِ «درخواستِ خراج» و «حقوقِ روزانه» رو فقط رو سرورِ واقعی می‌شه به‌عنوانِ چند بازیکن تست کرد
const mockTributes = []; // {id, from_id, from_name, from_role, to_id, to_name, amount, status, created_at, due_at, paid_at}
let mockTributeSeq = 1;
const ROLE_LABEL_FA = { coin: 'استاد سکه', warden: 'والی', overlord: 'بالادست' };
const mockBuildings = {}; // building_id -> { level, upgrade_to, ready_at } — قلعهٔ اصلیِ خودت
const mockCastleBuildings = {}; // castle_name -> (building_id -> state) — قلعه‌های اضافه (غنیمتِ جنگ/تصمیمِ ادمین)

function mockOwnedCastles() {
  return mockMe.castle ? [mockMe.castle, ...Object.keys(mockCastleBuildings)] : [];
}
// همهٔ قلعه‌های یک بازیکنِ دلخواه (خودم یا یکی از NPCها) — NPCها تو mock فقط همون
// یک قلعهٔ ثابتشون رو دارن (بدون قلعهٔ اضافه)، مگر اینکه از پنل ادمین قلعه‌شون گرفته شده باشه
function mockPlayerCastles(tgId) {
  if (tgId === 1) return mockOwnedCastles();
  const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
  return p && p.castle ? [p.castle] : [];
}
function mockCastleBuildingState(castle) {
  if (castle === mockMe.castle) return mockBuildings;
  return (mockCastleBuildings[castle] ||= {});
}
function mockAllBuildingLevels() {
  const total = {};
  for (const castle of mockOwnedCastles()) {
    for (const [id, st] of Object.entries(mockCastleBuildingState(castle))) {
      if (st.level) total[id] = (total[id] || 0) + st.level;
    }
  }
  return total;
}
function mockResolveCastleUpgrades(state) {
  const now = Date.now();
  for (const st of Object.values(state)) {
    if (st.upgrade_to && st.ready_at && new Date(st.ready_at).getTime() <= now) {
      st.level = st.upgrade_to; st.upgrade_to = null; st.ready_at = null;
    }
  }
}
const mockAlliances = [
  // یک اتحاد تجاری از قبل پذیرفته‌شده — برای تست کاروان بدون نیاز به شبیه‌سازی طرف مقابل
  { id: 'a1', mine_proposed: false, other_id: 9002, other_name: 'تایوین لنیستر', type: 'trade', type_name: 'پیمان تجاری', name: '', public: true, status: 'accepted' },
]; // {id, mine_proposed, other_id, other_name, type, type_name, name, public, status}
let mockAllianceSeq = 1;
let mockLastFeast = null;
let mockWarWindowOpen = true; // پیش‌فرض باز — تا ادمین صریحاً نبندتش
const mockCampaigns = []; // {id, origin_castle, op_type, target_castle, troops, gold_cost, men_committed, food_per_day, active, created_at, last_food_tick, travel_minutes, arrival_at}
let mockCampaignSeq = 1;
const mockCaravans = []; // {id, from, to, from_castle, to_castle, resources, active, arrived, travel_minutes, arrival_at, created_at}
let mockCaravanSeq = 1;
const mockMarket = [
  { resource: 'wood', qty: 400, price: 3, prev_price: 3, base_price: 3 },
  { resource: 'stone', qty: 300, price: 4, prev_price: 4, base_price: 4 },
  { resource: 'iron', qty: 200, price: 6, prev_price: 6, base_price: 6 },
  { resource: 'food', qty: 500, price: 2, prev_price: 2, base_price: 2 },
  { resource: 'wine', qty: 120, price: 8, prev_price: 8, base_price: 8 },
];
const mockBlackMarket = [
  { id: 'bm1', resource: 'wine', qty: 40, price: 5, expires_at: Date.now() + 3 * 3600 * 1000 },
];
let mockBlackMarketSeq = 2;
const DEFAULT_MOCK_PLAYER_RESOURCES = {
  gold: 1000, wood: 150, stone: 100, iron: 100, food: 800, wine: 30, men: 500,
  weapon_sword: 20, weapon_spear: 20, weapon_archer: 20, weapon_lcav: 20, weapon_hcav: 20,
};
const mockPlayerResources = {}; // tg_id -> {gold,wood,stone,iron,food,wine,men} — برای تست ویرایش منابع در پنل ادمین
const mockMapCastles = []; // {region, name, kind, terrain, x, y, custom}
const mockSpyMissions = []; // {id, target, travel_minutes, arrival_at, success, report, created_at}
let mockSpySeq = 1;
const mockRoleplays = []; // {id, category, text, result, resolved, created_at}
let mockRoleplaySeq = 1;
const mockItems = []; // {id, name, type, duration, duration_hours, description, created_at}
let mockItemSeq = 1;
const mockItemGrants = []; // {id, item_id, tg_id, color, granted_at, expires_at}
let mockItemGrantSeq = 1;
const mockRumors = []; // {id, author_tg_id, author_name, target_tg_id, target_name, text, created_at}
let mockRumorsSeenAt = 0;
let mockRumorSeq = 1;

function mockResolveRegion(name) {
  for (const [rid, r] of Object.entries(REGIONS_STATIC)) {
    if (r.castles.includes(name) || r.ports.includes(name)) return rid;
  }
  const custom = mockMapCastles.find(m => m.name === name);
  return custom ? custom.region : null;
}
// نوع زمینِ یک قلعه: land | coastal | sea — همان چیزی که ادمین از تب نقشه روی پینش
// مشخص کرده (mockMapCastles.terrain)، وگرنه پیش‌فرضِ استاتیک (castles→land, ports→coastal)
function mockCastleTerrain(name) {
  const custom = mockMapCastles.find(m => m.name === name);
  if (custom?.terrain) return custom.terrain;
  for (const r of Object.values(REGIONS_STATIC)) {
    if (r.ports.includes(name)) return DEFAULT_SEA_CASTLES.has(name) ? 'sea' : 'coastal';
    if (r.castles.includes(name)) return 'land';
  }
  if (custom) return custom.kind === 'port' ? 'coastal' : 'land';
  return 'land';
}
function mockIsPortCastle(name) {
  return mockCastleTerrain(name) !== 'land';
}
// نقشِ خراج‌گیریِ فعلیِ این tg_id (اگه داشته باشه) + مجموعهٔ زیردست‌های مستقیمش —
// آینهٔ my_tribute_role در backend/ranks.py
function mockMyTributeRole(tgId) {
  if (mockHierarchy.small_council.coin === tgId) {
    return { role: 'coin', targets: new Set(Object.values(mockHierarchy.wardens).filter(v => v != null)) };
  }
  for (const [gid, g] of Object.entries(WARDEN_GROUPS)) {
    if (mockHierarchy.wardens[gid] === tgId) {
      const targets = new Set(g.regions.map(r => mockHierarchy.overlords[r]).filter(v => v != null));
      return { role: 'warden', targets };
    }
  }
  for (const [rid, holder] of Object.entries(mockHierarchy.overlords)) {
    if (holder === tgId) {
      const targets = new Set(MOCK_PLAYERS.filter(p => mockResolveRegion(p.castle) === rid).map(p => p.tg_id));
      if (mockMe.registered && mockResolveRegion(mockMe.castle) === rid && tgId !== 1) targets.add(1);
      return { role: 'overlord', targets };
    }
  }
  return { role: null, targets: new Set() };
}
const mockPolls = [
  { id: 'p1', question: 'بالادستی ریچ چه کسی باشد؟', options: ['مارگری تایرل', 'راندیل تارلی'],
    status: 'open', tally: [3, 1], total_votes: 4, eligible: true, my_vote: null },
];
const MOCK_PLAYERS = [
  { tg_id: 9001, name: 'دنریس تارگرین', castle: 'دراگون استون', region: 'crown', region_name: 'کراون‌لندز', title: 'ملکه' },
  { tg_id: 9002, name: 'تایوین لنیستر', castle: 'کرگ', region: 'west', region_name: 'وسترلندز', title: 'لرد' },
  { tg_id: 9003, name: 'مارگری تایرل', castle: 'هایگاردن', region: 'reach', region_name: 'ریچ', title: 'لیدی' },
  { tg_id: 9004, name: 'یارا گریجوی', castle: 'پایک', region: 'iron', region_name: 'جزایر آهن', title: 'لیدی' },
  { tg_id: 9005, name: 'ادموری تالی', castle: 'ریوران', region: 'river', region_name: 'ریورلندز', title: 'لرد' },
];

function mockResolve() {
  mockResolveCastleUpgrades(mockBuildings);
  for (const state of Object.values(mockCastleBuildings)) mockResolveCastleUpgrades(state);
}

// تولیدِ روزانه (طلا/غذا/... بر اساس لولِ ساختمان‌ها) به‌نسبتِ زمانِ واقعاً گذشته از آخرین
// چک اعمال می‌شه — آینه‌ی apply_production در backend/game.py. مقدارِ اعشاریِ دقیق تو
// mockMe.resources می‌مونه (که تولیدِ کم‌مقدار بینِ چک‌های پیاپی گم نشه)، فقط موقعِ
// برگردوندن به فرانت (تابعِ me()) رند می‌شه
function mockEffectiveCaps() {
  const caps = { ...RESOURCE_CAPS };
  for (const [id, level] of Object.entries(mockAllBuildingLevels())) {
    const { cap_bonus } = buildingYield(id, level);
    for (const [k, v] of Object.entries(cap_bonus)) caps[k] = (caps[k] || 0) + v;
  }
  return caps;
}

// مقدارهای مثبت رو به resources بازیکن اضافه می‌کنه بدون رد شدن از سقفِ مؤثرش —
// آینه‌ی add_resources در backend/game.py
function mockAddResources(deltas) {
  if (!mockMe.resources) return;
  const caps = mockEffectiveCaps();
  for (const [k, delta] of Object.entries(deltas)) {
    if (!delta) continue;
    const cap = caps[k] ?? 1e9;
    mockMe.resources[k] = Math.min(cap, (mockMe.resources[k] || 0) + delta);
  }
}

function mockApplyProduction() {
  if (!mockMe.resources) return;
  const last = new Date(mockMe.last_tick || Date.now()).getTime();
  const elapsedDays = (Date.now() - last) / 86400000;
  if (elapsedDays <= 0) return;

  const prod = { ...DAILY_PRODUCTION };
  const caps = mockEffectiveCaps();
  for (const [id, level] of Object.entries(mockAllBuildingLevels())) {
    const { produces } = buildingYield(id, level);
    for (const [k, v] of Object.entries(produces)) prod[k] = (prod[k] || 0) + v;
  }
  const popularity = Math.max(0, Math.min(100, mockMe.popularity ?? POPULARITY_START));
  prod.men = (prod.men || 0) * (0.5 + popularity / 100);
  const men = mockMe.resources.men || 0;
  const taxRate = Math.max(0, Math.min(100, mockMe.tax_rate ?? TAX_RATE_DEFAULT));
  const multiplier = taxYieldMultiplier(mockMe.popularity ?? POPULARITY_START);
  prod.gold = (prod.gold || 0) + Math.round(men * (taxRate / 100) * multiplier);

  for (const [k, perDay] of Object.entries(prod)) {
    const cap = caps[k] ?? 1e9;
    mockMe.resources[k] = Math.min(cap, (mockMe.resources[k] || 0) + perDay * elapsedDays);
  }
  mockMe.last_tick = new Date().toISOString();
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

function mockTroopName(tid) {
  return COMMON_TROOPS.find(t => t.id === tid)?.name || NAVAL_TROOPS.find(t => t.id === tid)?.name || tid;
}

function mockStationedOrigins() {
  const nowMs = Date.now();
  return mockCampaigns
    .filter(c => c.active && c.op_type === 'garrison' && new Date(c.arrival_at).getTime() <= nowMs)
    .map(c => c.target_castle);
}

function mockBuiltLevels(castle) {
  const state = castle ? mockCastleBuildingState(castle) : mockBuildings;
  return Object.fromEntries(Object.entries(state).map(([k, v]) => [k, v.level || 0]));
}
function mockCanAfford(cost) {
  return Object.entries(cost).every(([k, v]) => (mockMe.resources?.[k] ?? 0) >= v);
}
function mockPay(cost) {
  for (const [k, v] of Object.entries(cost)) mockMe.resources[k] -= v;
}
function rumorBrief(r) {
  const reactions = r.reactions || {};
  const values = Object.values(reactions);
  return {
    id: r.id, target: r.target_name, target_tg_id: r.target_tg_id,
    text: r.text, created_at: r.created_at, mine: r.author_tg_id === 1,
    likes: values.filter(v => v === 'like').length,
    dislikes: values.filter(v => v === 'dislike').length,
    my_reaction: reactions[1] ?? null,
  };
}
const M = {
  gamedata: { regions: REGIONS_STATIC },
  me: () => {
    if (mockMe.registered && !mockMe.pending) {
      mockResolveCampaigns();
      // اول ارتقاهای تمام‌شده نهایی می‌شن، بعد تولید — وگرنه تولیدِ فاصلهٔ زمانیِ
      // سپری‌شده با سطحِ قدیمی (پیش‌از-ارتقا) حساب می‌شه
      mockResolve();
      mockApplyProduction();
      mockMe.active_campaigns = mockCampaigns.filter(c => c.active).length;
      return {
        ...mockMe, castles: Object.keys(mockCastleBuildings),
        resources: Object.fromEntries(Object.entries(mockMe.resources).map(([k, v]) => [k, Math.round(v)])),
        resource_caps: mockEffectiveCaps(),
      };
    }
    return mockMe;
  },
  register: (b) => {
    Object.assign(mockMe, {
      registered: true, pending: true, name: b.name,
      gender: b.gender, title: DEFAULT_TITLE[b.gender],
      admin_role: 'full', // حالت mock تک‌بازیکنه — خودت همیشه ادمینی تا بتونی خاندان خودت رو تخصیص بدی
      is_owner: true,
      requested_castles: (b.requested_castles || []).slice(0, 5),
      backstory: b.backstory || '', profile_image: b.profile_image || null,
      last_tick: new Date().toISOString(),
    });
    return { ok: true };
  },
  adminListPendingPlayers: () => (mockMe.registered && mockMe.pending)
    ? [{
        tg_id: 1, name: mockMe.name, title: mockMe.title, gender: mockMe.gender,
        requested_castles: (mockMe.requested_castles || []).map(name => ({
          name, region: mockResolveRegion(name),
          occupied: MOCK_PLAYERS.some(p => p.castle === name),
        })),
      }] : [],
  adminListRoster: () => {
    const out = [];
    if (mockMe.registered && !mockMe.pending) {
      out.push({
        tg_id: 1, name: mockMe.name, title: mockMe.title, region: mockMe.region, region_name: mockMe.region_name,
        castle: mockMe.castle, is_port: mockMe.is_port, house: CASTLE_HOUSES[mockMe.castle] || null,
        castles: Object.keys(mockCastleBuildings),
      });
    }
    for (const p of MOCK_PLAYERS) {
      if (!p.castle) continue; // قلعه‌اش رو از دست داده (مثلاً تو mock تصرف شده)
      out.push({ tg_id: p.tg_id, name: p.name, title: p.title, region: mockResolveRegion(p.castle), region_name: p.region_name, castle: p.castle, is_port: false, house: CASTLE_HOUSES[p.castle] || null, castles: [] });
    }
    return out;
  },
  adminAddCastle: (tgId, castle) => {
    if (tgId !== 1) throw new Error('در حالت آزمایشی (بدون سرور) فقط می‌توانی خودت را تخصیص بدهی');
    if (!mockMe.registered || mockMe.pending) throw new Error('اول باید خاندان و قلعهٔ اصلی داشته باشد');
    const allCastles = Object.values(REGIONS_STATIC).flatMap(r => [...r.castles, ...r.ports]);
    if (!allCastles.includes(castle)) throw new Error('این قلعه در بازی شناخته‌شده نیست');
    if (castle === mockMe.castle || castle in mockCastleBuildings) throw new Error('این قلعه از قبل مالِ همین بازیکن است');

    let capturedFrom = null;
    const npc = MOCK_PLAYERS.find(p => p.castle === castle);
    if (npc) {
      capturedFrom = npc.name;
      npc.castle = null; // در mock فقط قلعهٔ اصلیِ NPCها هست، پس بدونِ قلعه می‌مونه
    }
    mockCastleBuildings[castle] = {};
    return { ok: true, captured_from: capturedFrom };
  },
  adminRemoveCastle: (tgId, castle) => {
    if (tgId !== 1) throw new Error('در حالت آزمایشی (بدون سرور) فقط می‌توانی قلعه‌های خودت را پس بدهی');
    if (!(castle in mockCastleBuildings)) throw new Error('این قلعه جزوِ قلعه‌های اضافهٔ این بازیکن نیست');
    delete mockCastleBuildings[castle];
    return { ok: true };
  },
  adminAssignHouse: (tgId, region, castle) => {
    if (tgId !== 1) throw new Error('در حالت آزمایشی (بدون سرور) فقط می‌توانی خودت را تخصیص بدهی');
    if (!mockMe.registered) throw new Error('این بازیکن پیدا نشد');
    if (!REGIONS_STATIC[region]) throw new Error('اقلیم نامعتبر');
    const r = REGIONS_STATIC[region];
    if (![...r.castles, ...r.ports].includes(castle)) throw new Error('این قلعه در این اقلیم نیست');
    const takenByNpc = MOCK_PLAYERS.some(p => p.castle === castle);
    if (takenByNpc) throw new Error('این قلعه صاحب دارد — یکی دیگر برگزین');
    const wasPending = mockMe.pending;
    Object.assign(mockMe, {
      pending: false, region, region_name: r.name, castle,
      house: CASTLE_HOUSES[castle] || null,
      is_port: mockCastleTerrain(castle) !== 'land',
      admin_role: 'full', // حالت mock تک‌بازیکنه — پنل ادمین همیشه برای تست محلی در دسترسه
      resources: mockMe.resources || {
        gold: 1000, food: 800, men: 500, iron: 100, stone: 100, wood: 150, wine: 30,
        weapon_sword: 20, weapon_spear: 20, weapon_archer: 20, weapon_lcav: 20, weapon_hcav: 20,
      },
      points: mockMe.points ?? 100, alliance_count: mockMe.alliance_count ?? 0,
      popularity: mockMe.popularity ?? POPULARITY_START, tax_rate: mockMe.tax_rate ?? TAX_RATE_DEFAULT,
      rank: mockMe.rank ?? 5, total_players: 12, day: mockMe.day ?? 18, season_length: 30,
    });
    return { ok: true, moved: !wasPending };
  },
  adminUnassignHouse: (tgId) => {
    if (tgId !== 1) throw new Error('در حالت آزمایشی (بدون سرور) فقط می‌توانی خودت را از خاندان خارج کنی');
    if (!mockMe.registered || mockMe.pending) throw new Error('این بازیکن اصلاً خاندانی ندارد');
    Object.assign(mockMe, { pending: true, region: null, region_name: null, castle: null, is_port: false });
    for (const k of Object.keys(mockCastleBuildings)) delete mockCastleBuildings[k];
    return { ok: true };
  },
  adminDeletePendingPlayer: (tgId) => {
    if (tgId !== 1) throw new Error('در حالت آزمایشی (بدون سرور) فقط می‌توانی خودت را حذف کنی');
    if (!mockMe.registered || !mockMe.pending) throw new Error('این بازیکن وارد بازی شده — اول باید از خاندانش خارجش کنی');
    Object.assign(mockMe, { registered: false, pending: false });
    return { ok: true };
  },
  setTax: (rate) => {
    if (rate < 0 || rate > 100) throw new Error('نرخ مالیات باید بین ۰ تا ۱۰۰ درصد باشد');
    mockMe.tax_rate = rate;
    return { ok: true, tax_rate: rate };
  },
  map: () => {
    mockResolveCampaigns();
    const pactByTgid = {};
    for (const a of mockAlliances) {
      if (a.status !== 'accepted') continue;
      const prev = pactByTgid[a.other_id];
      if (!prev || PACT_PRIORITY.indexOf(a.type) < PACT_PRIORITY.indexOf(prev)) pactByTgid[a.other_id] = a.type;
    }
    // اقلیمِ نمایش‌داده‌شده برای هر پین، از رویِ خودِ اقلیمِ همون قلعه‌ست (نه اقلیمِ
    // خانگیِ صاحبش) — یه لرد می‌تونه قلعهٔ دومی در اقلیمِ دیگه‌ای داشته باشه
    const owners = {};
    for (const p of MOCK_PLAYERS) {
      if (!p.castle) continue;
      owners[p.castle] = { tg_id: p.tg_id, name: p.name, title: p.title, points: 500 + p.tg_id % 500, overlord_name: null, region: mockResolveRegion(p.castle) || p.region, pact: pactByTgid[p.tg_id] || null };
    }
    if (mockMe.registered && !mockMe.pending) {
      for (const c of mockOwnedCastles()) {
        owners[c] = { tg_id: 1, name: mockMe.name, title: mockMe.title, points: mockMe.points, overlord_name: null, region: mockResolveRegion(c) || mockMe.region, pact: null };
      }
    }
    const nowMs = Date.now();
    return {
      regions: Object.entries(REGIONS_STATIC).map(([id, r]) => {
        const custom = mockMapCastles.filter(m => m.region === id && m.custom);
        const coords = {};
        const kindByName = {};
        for (const m of mockMapCastles.filter(m => m.region === id)) { coords[m.name] = [m.x, m.y]; kindByName[m.name] = m.kind; }
        return {
          id, name: r.name,
          castles: [
            ...r.castles.map(n => ({ name: n, owner: owners[n] || null, port: mockCastleTerrain(n) !== 'land', kind: kindByName[n] || 'castle', house: CASTLE_HOUSES[n] || null, terrain: mockCastleTerrain(n) })),
            ...r.ports.map(n => ({ name: n, owner: owners[n] || null, port: mockCastleTerrain(n) !== 'land', kind: kindByName[n] || 'port', house: CASTLE_HOUSES[n] || null, terrain: mockCastleTerrain(n) })),
            ...custom.map(c => ({ name: c.name, owner: owners[c.name] || null, port: mockCastleTerrain(c.name) !== 'land', kind: c.kind, house: CASTLE_HOUSES[c.name] || null, terrain: mockCastleTerrain(c.name) })),
          ],
          coords,
        };
      }),
      campaigns: [
        { from: 'کسترلی راک', to: 'ریورران', op_type: 'attack', name: 'حملهٔ نظامی', mine: false, revealed_minutes_ago: 23, travel_minutes: 45, arrived: true },
        { from: 'پایک', to: 'وایت هاربر', op_type: 'naval_raid', name: 'غارت دریایی', mine: false, revealed_minutes_ago: 61, travel_minutes: 65, arrived: false },
        ...mockCampaigns.filter(c => c.active).map(c => ({
          from: c.origin_castle, to: c.target_castle, op_type: c.op_type, name: c.name, mine: true,
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
      ...r.castles.filter(n => !placed.has(n)).map(n => ({ name: n, kind: 'castle', terrain: 'land' })),
      ...r.ports.filter(n => !placed.has(n)).map(n => ({ name: n, kind: 'port', terrain: 'coastal' })),
    ];
  },
  adminAddMapCastle: (body) => {
    const r = REGIONS_STATIC[body.region];
    if (!r) throw new Error('اقلیم نامعتبر');
    if (!(body.x >= 0 && body.x <= 100 && body.y >= 0 && body.y <= 100)) throw new Error('مختصات نامعتبر');
    const allNames = new Set(mockMapCastles.map(m => m.name));
    for (const reg of Object.values(REGIONS_STATIC)) { reg.castles.forEach(n => allNames.add(n)); reg.ports.forEach(n => allNames.add(n)); }

    let name, custom;
    if (body.new_name && body.new_name.trim()) {
      name = body.new_name.trim().slice(0, 40);
      if (allNames.has(name)) throw new Error('این اسم قبلاً در بازی وجود دارد');
      custom = true;
    } else {
      name = (body.name || '').trim();
      if (![...r.castles, ...r.ports].includes(name)) throw new Error('این قلعه/بندر در دیتای این اقلیم نیست');
      if (mockMapCastles.some(m => m.region === body.region && m.name === name)) throw new Error('این قلعه از قبل روی نقشه گذاشته شده');
      custom = false;
    }
    // نوع آیکن (قلعه/شهر/مخروبه/بندر) و نوع زمین (خشکی/خشکی‌دریایی/دریایی) را ادمین دستی مشخص می‌کند
    const kind = ['castle', 'city', 'ruin', 'port'].includes(body.kind) ? body.kind : 'castle';
    const terrain = MAP_TERRAINS.some(t => t.key === body.terrain) ? body.terrain : 'land';
    mockMapCastles.push({ region: body.region, name, kind, terrain, x: body.x, y: body.y, custom });
    return { ok: true, name };
  },
  adminDeleteMapCastle: (name) => {
    const i = mockMapCastles.findIndex(m => m.name === name);
    if (i === -1) throw new Error('این نشانه روی نقشه پیدا نشد');
    mockMapCastles.splice(i, 1);
    return { ok: true };
  },
  adminEditMapCastle: (name, body) => {
    const m = mockMapCastles.find(m => m.name === name);
    if (!m) throw new Error('این نشانه روی نقشه پیدا نشد');
    const kind = ['castle', 'city', 'ruin', 'port'].includes(body.kind) ? body.kind : 'castle';
    const terrain = MAP_TERRAINS.some(t => t.key === body.terrain) ? body.terrain : 'land';
    m.kind = kind; m.terrain = terrain;
    if (mockMe.registered && mockMe.castle === name) mockMe.is_port = terrain !== 'land';
    return { ok: true };
  },
  submitCampaign: (body) => {
    mockResolveCampaigns();
    const op = OP_TYPES.find(o => o.id === body.op_type);
    if (!op) throw new Error('نوع عملیات نامعتبر');
    if (!mockWarWindowOpen) throw new Error('پنجرهٔ لشکرکشی الان بسته است — ادمین باید بازش کند تا بتوانی فرمان گسیل بدهی');

    const validOrigins = [mockMe.castle, ...Object.keys(mockCastleBuildings), ...mockStationedOrigins()];
    if (!validOrigins.includes(body.origin_castle)) {
      throw new Error('مبدا باید قلعهٔ خودت یا جایی باشد که لشکرت همین الان مستقر است');
    }

    let targetCastle = body.origin_castle;
    if (op.needsTarget) {
      if (!body.target_castle) throw new Error('مقصد را مشخص کن');
      targetCastle = body.target_castle;
      if (op.portOnly) {
        if (!mockIsPortCastle(targetCastle)) throw new Error('غارت دریایی فقط علیه اهداف بندری ممکن است');
        if (!mockIsPortCastle(body.origin_castle)) throw new Error('غارت دریایی فقط از قلعه/شهرهای بندری ممکن است — لشکرکشی از راه آبی');
        if (!Object.entries(body.troops || {}).some(([tid, n]) => NAVAL_TROOP_IDS.includes(tid) && n > 0)) {
          throw new Error('غارت دریایی باید با کشتی انجام شود — این فرمان هیچ کشتی‌ای همراه ندارد');
        }
      }
      if (op.landOnly && mockIsPortCastle(targetCastle)) {
        throw new Error('محاصره فقط علیه قلعه‌های غیربندری معنا دارد — برای هدف‌های بندری از غارت دریایی استفاده کن');
      }
    }

    const originBuildings = mockCastleBuildingState(body.origin_castle);
    const originIsPort = mockCastleTerrain(body.origin_castle) !== 'land';
    // نیروهای ویژهٔ قابل‌ساخت بر اساسِ اقلیمِ واقعیِ خودِ قلعهٔ مبدا — نه اقلیمِ خانگیِ
    // بازیکن، چون قلعهٔ دوم می‌تونه در اقلیمِ دیگه‌ای باشه
    const originRegion = mockResolveRegion(body.origin_castle) || mockMe.region;
    const specials = REGIONS_STATIC[originRegion]?.special || [];
    let gold = 0, men = 0, food = 0;
    const weapons = {};
    for (const [tid, n] of Object.entries(body.troops || {})) {
      if (!n || n <= 0) continue;
      const common = COMMON_TROOPS.find(t => t.id === tid);
      if (common) {
        const req = TROOP_UNIT_BUILDINGS[tid];
        if (req) {
          const campLevel = originBuildings[req.camp]?.level || 0;
          if (campLevel <= 0) {
            throw new Error(`برای گسیل ${common.name} باید ${BUILDINGS_STATIC[req.camp].name} را ساخته باشی`);
          }
          if (req.weapon) weapons[req.weapon] = (weapons[req.weapon] || 0) + n * WEAPON_PER_SOLDIER;
        }
        gold += common.cost * n;
        food += (common.food ?? FOOD_COST_REGULAR) * n;
      } else if (NAVAL_TROOP_IDS.includes(tid)) {
        const naval = NAVAL_TROOPS.find(t => t.id === tid);
        if (!originIsPort) throw new Error('فقط قلعه/شهرهای خشکی‌دریایی یا کاملاً دریایی می‌توانند کشتی بسازند');
        const portLevel = originBuildings[NAVAL_CAMP_BUILDING]?.level || 0;
        if (portLevel <= 0) throw new Error(`برای ساخت ${naval.name} باید ${BUILDINGS_STATIC[NAVAL_CAMP_BUILDING].name} را بنا کرده باشی`);
        gold += naval.cost * n;
        food += (naval.food ?? FOOD_COST_SPECIAL) * n;
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
    for (const [wkey, needed] of Object.entries(weapons)) {
      if ((mockMe.resources[wkey] ?? 0) < needed) {
        throw new Error(`${WEAPON_NAMES[wkey]} کافی نداری — کارگاه تسلیحاتش را بساز یا صبر کن بیشتر تولید شود`);
      }
    }

    const navalCapacity = Object.entries(body.troops || {})
      .filter(([tid, n]) => NAVAL_TROOP_IDS.includes(tid) && n > 0)
      .reduce((s, [tid, n]) => s + NAVAL_TROOPS.find(t => t.id === tid).capacity * n, 0);
    const landMen = Object.entries(body.troops || {})
      .filter(([tid, n]) => !NAVAL_TROOP_IDS.includes(tid) && n > 0)
      .reduce((s, [, n]) => s + n, 0);

    const sameCastle = targetCastle === body.origin_castle;
    if (!sameCastle && mockCastleTerrain(body.origin_castle) === 'sea' && landMen > navalCapacity) {
      throw new Error(`این قلعه کاملاً دریایی است و راهی به خشکی ندارد — کشتی‌های این فرمان فقط ${navalCapacity} نفر را جابه‌جا می‌کنند، کشتی بیشتری اضافه کن یا نیروی کمتری بفرست`);
    }

    mockPay({ gold, ...weapons });
    mockMe.resources.men -= men;

    let travel, routePath;
    if (sameCastle) {
      travel = 0; routePath = [body.origin_castle];
    } else {
      const opts = travelRoutes(body.origin_castle, targetCastle, 2, true, mockCastleTerrain);
      const chosen = (body.via && opts.find(r => r.path.join('→') === body.via.join('→'))) || opts[0] || { minutes: travelMinutes(sameCastle, body.origin_castle, targetCastle), path: [body.origin_castle, targetCastle], via_sea: pathUsesSea([body.origin_castle, targetCastle], mockCastleTerrain) };
      if (chosen.via_sea && landMen > navalCapacity) {
        const landOpts = travelRoutes(body.origin_castle, targetCastle, 2, false, mockCastleTerrain);
        if (landOpts.length) {
          throw new Error('این مسیر از آب می‌گذرد و کشتی‌های این فرمان ظرفیتِ کافی برای حملِ همهٔ نیروهای زمینی را ندارند — یا کشتی بیشتری اضافه کن، یا مسیرِ زمینیِ دیگری که از /war/routes پیشنهاد می‌شود انتخاب کن');
        }
        throw new Error(`این مسیر فقط از راهِ آب ممکن است و کشتی‌های این فرمان فقط ${navalCapacity} نفر را جابه‌جا می‌کنند — کشتی بیشتری اضافه کن یا نیروی کمتری بفرست`);
      }
      travel = chosen.minutes; routePath = chosen.path;
    }

    const power = campaignPower(body.troops, mockBuiltLevels(body.origin_castle));
    const nowIso = new Date().toISOString();
    const doc = {
      id: String(mockCampaignSeq++), tg_id: 1, player_name: mockMe.name,
      origin_castle: body.origin_castle, op_type: body.op_type, target_castle: targetCastle,
      name: (body.name || '').trim().slice(0, 60) || op.name, troops: body.troops, power,
      gold_cost: gold, men_committed: men, food_per_day: food,
      active: true, created_at: nowIso, last_food_tick: nowIso, arrival_notified: false,
      travel_minutes: travel, route_path: routePath, arrival_at: new Date(Date.now() + travel * 60000).toISOString(),
    };
    mockCampaigns.push(doc);
    return { ok: true, id: doc.id, gold_cost: gold, men_committed: men, food_per_day: food, travel_minutes: travel, route_path: routePath, power };
  },
  warRoutes: (origin, target) => {
    if (origin === target) return { routes: [{ minutes: 0, path: [origin] }] };
    const opts = travelRoutes(origin, target, 2, true, mockCastleTerrain);
    if (!opts.length) throw new Error('مسیری بین این دو قلعه پیدا نشد');
    return { routes: opts };
  },
  cancelCampaign: (id) => {
    const c = mockCampaigns.find(x => x.id === id);
    if (!c) throw new Error('لشکر پیدا نشد');
    if (!c.active) throw new Error('این لشکر دیگر فعال نیست');
    c.active = false;
    const weaponsRefund = {};
    for (const [tid, n] of Object.entries(c.troops || {})) {
      if (!n || n <= 0) continue;
      const weaponKey = TROOP_UNIT_BUILDINGS[tid]?.weapon;
      if (weaponKey) weaponsRefund[weaponKey] = (weaponsRefund[weaponKey] || 0) + n * WEAPON_PER_SOLDIER;
    }
    mockAddResources({ men: c.men_committed, gold: c.gold_cost, ...weaponsRefund });
    return { ok: true, men_refunded: c.men_committed, gold_refunded: c.gold_cost, weapons_refunded: weaponsRefund };
  },
  warWindow: () => ({ open: mockWarWindowOpen, updated_at: null }),
  adminGetWarWindow: () => ({ open: mockWarWindowOpen, updated_at: null, updated_by: null }),
  adminSetWarWindow: (open) => {
    if (mockWarWindowOpen === open) throw new Error(`پنجرهٔ لشکرکشی همین الان هم ${open ? 'باز' : 'بسته'} است`);
    mockWarWindowOpen = open;
    mockSendSystemMessage(
      open
        ? 'پنجرهٔ لشکرکشی باز شد — از این لحظه می‌توانی فرمان گسیل نیرو بدهی.'
        : 'پنجرهٔ لشکرکشی بسته شد — تا اطلاع بعدی فرمان گسیل نیروی تازه ممکن نیست؛ لشکرهایی که در راهند دست‌نخورده می‌مانند.',
    );
    return { ok: true, open };
  },
  adminAnnounceEvent: (title, description) => {
    const t = (title || '').trim().slice(0, 80);
    const d = (description || '').trim().slice(0, 1500);
    if (!t || !d) throw new Error('عنوان و توضیحِ رویداد نمی‌توانند خالی باشند');
    mockSendSystemMessage(`🎉 رویداد: ${t}\n\n${d}`);
    return { ok: true };
  },
  adminAwardStoryteller: (tgId, tier, reason = '') => ({ ok: true, medals: [{ key: 'realm_storyteller', name: 'راوی قلمرو', icon: '📜', tier, title: tier === 'gold' ? 'زبان تاریخ' : tier === 'silver' ? 'وقایع‌نگار' : 'قصه‌گو' }] }),
  adminAwardSpecialMedal: (tgId, medal) => ({ ok: true, medals: [{ key: 'special_mock', ...medal }] }),
  adminSendBotMessage: (text, sendToAll, toTgIds = []) => {
    const message = (text || '').trim().slice(0, 4000);
    if (!message) throw new Error('متن پیام نمی‌تواند خالی باشد');
    const ids = [...new Set(toTgIds)];
    if (!sendToAll && ids.length === 0) throw new Error('حداقل یک بازیکن را انتخاب کن');
    return { ok: true, sent_to: sendToAll ? MOCK_PLAYERS.length + 1 : ids.length };
  },
  legions: () => {
    mockResolveCampaigns();
    const nowMs = Date.now();
    return mockCampaigns.slice().reverse()
      .filter(c => c.active)
      .map(c => ({
        id: c.id,
        op_type: c.op_type, op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        name: c.name || OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        origin: c.origin_castle, target: c.target_castle,
        troops: Object.entries(c.troops || {}).filter(([, n]) => n > 0).map(([tid, n]) => ({
          name: mockTroopName(tid), count: n,
        })),
        men_committed: c.men_committed, power: c.power || 0,
        travel_minutes: c.travel_minutes, route_path: c.route_path,
        arrived: nowMs >= new Date(c.arrival_at).getTime(),
        can_relaunch: c.op_type === 'garrison' && nowMs >= new Date(c.arrival_at).getTime(),
        created_at: c.created_at, arrival_at: c.arrival_at,
      }));
  },
  warMine: () => {
    // گزارش‌ها عمداً حداقلی‌اند: فقط اسم، فرستنده، مبدا/مقصد و زمان رسیدن — نه توان نه نیرو.
    // لشکر دفاعی (همون‌جایی) اصلاً وارد گزارش‌ها نمی‌شود.
    mockResolveCampaigns();
    const nowMs = Date.now();
    return mockCampaigns.slice().reverse()
      .filter(c => c.op_type !== 'defense')
      .filter(c => {
        const arrived = nowMs >= new Date(c.arrival_at).getTime();
        if (!arrived) return true;
        return nowMs - new Date(c.arrival_at).getTime() <= REPORT_VISIBLE_HOURS * 3600000;
      })
      .map(c => ({
        id: c.id,
        op_type: c.op_type, op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        name: c.name || OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        sender: c.player_name,
        origin: c.origin_castle, target: c.target_castle,
        active: c.active,
        travel_minutes: c.travel_minutes, route_path: c.route_path, arrived: nowMs >= new Date(c.arrival_at).getTime(),
        created_at: c.created_at, arrival_at: c.arrival_at,
      }));
  },
  playerCastles: (tgId) => mockPlayerCastles(tgId),
  sendCaravan: (body) => {
    const partner = mockAlliances.find(a => a.other_id === body.target_tg_id && a.status === 'accepted'
      && (a.type === 'trade' || a.type === 'full_alliance'));
    if (!partner) throw new Error('فقط با هم‌پیمان‌های تجاری (پیمان تجاری یا اتحاد کامل) می‌تونی کاروان رد و بدل کنی');
    const p = MOCK_PLAYERS.find(x => x.tg_id === body.target_tg_id);
    if (!p) throw new Error('گیرنده پیدا نشد');

    const originCastle = body.origin_castle || mockMe.castle;
    if (!mockOwnedCastles().includes(originCastle)) throw new Error('این قلعه مالِ تو نیست');
    const targetCastle = body.target_castle || p.castle;
    if (!mockPlayerCastles(p.tg_id).includes(targetCastle)) throw new Error('این قلعه مالِ گیرنده نیست');

    const cost = {};
    for (const [good, qty] of Object.entries(body.resources || {})) {
      if (!TRADE_GOODS.includes(good)) throw new Error(`کالای نامعتبر: ${good}`);
      if (qty > 0) cost[good] = qty;
    }
    if (!Object.keys(cost).length) throw new Error('هیچ کالایی برای فرستادن انتخاب نکردی');
    mockApplyProduction();
    if (!mockCanAfford(cost)) throw new Error('این مقدار کالا رو نداری');
    mockPay(cost);

    const travel = travelMinutes(originCastle === targetCastle, originCastle, targetCastle);
    const nowIso = new Date().toISOString();
    mockCaravans.push({
      id: String(mockCaravanSeq++), mine_sent: true,
      from: mockMe.name, to: p.name, from_castle: originCastle, to_castle: targetCastle,
      resources: cost, active: true, travel_minutes: travel,
      arrival_at: new Date(Date.now() + travel * 60000).toISOString(), created_at: nowIso,
    });
    return { ok: true, travel_minutes: travel };
  },
  myCaravans: () => {
    const nowMs = Date.now();
    return mockCaravans.slice().reverse().map(c => ({
      id: c.id, mine_sent: c.mine_sent,
      from: c.from, to: c.to, from_castle: c.from_castle, to_castle: c.to_castle,
      resources: Object.fromEntries(Object.entries(c.resources).map(([k, v]) => [TRADE_GOOD_NAMES[k] || k, v])),
      travel_minutes: c.travel_minutes, arrived: nowMs >= new Date(c.arrival_at).getTime(),
      created_at: c.created_at,
    }));
  },
  market: () => mockMarket.filter(m => m.qty > 0).map(m => ({
    resource: m.resource, name: TRADE_GOOD_NAMES[m.resource] || m.resource, qty: m.qty, price: m.price,
    change_pct: m.prev_price ? Math.round((m.price - m.prev_price) / m.prev_price * 1000) / 10 : 0,
  })),
  marketBuy: (resource, qty) => {
    const m = mockMarket.find(x => x.resource === resource);
    if (!m || m.qty <= 0) throw new Error('این کالا در بازار وستروس موجود نیست');
    if (qty <= 0) throw new Error('مقدار نامعتبر');
    if (qty > m.qty) throw new Error(`فقط ${m.qty} واحد از این کالا در بازار مانده`);
    mockApplyProduction();
    const cost = qty * m.price;
    if (!mockCanAfford({ gold: cost })) throw new Error('طلای کافی نداری');
    mockPay({ gold: cost });
    mockAddResources({ [resource]: qty });
    m.qty -= qty;
    m.price = Math.max(1, Math.round(Math.min(m.price * (1 + 0.015 * qty), m.base_price * 2)));
    return { ok: true, resource, qty, cost };
  },
  blackMarket: () => mockBlackMarket.filter(m => m.qty > 0 && m.expires_at > Date.now()).map(m => ({
    id: m.id, resource: m.resource, name: TRADE_GOOD_NAMES[m.resource] || m.resource, qty: m.qty, price: m.price,
    expires_in_minutes: Math.max(0, Math.floor((m.expires_at - Date.now()) / 60000)),
  })),
  blackMarketBuy: (listingId, qty) => {
    const m = mockBlackMarket.find(x => x.id === listingId);
    if (!m || m.qty <= 0 || m.expires_at <= Date.now()) throw new Error('این کالای بازار سیاه دیگر موجود نیست');
    if (qty <= 0 || qty > m.qty) throw new Error('مقدار نامعتبر یا بیشتر از موجودی');
    mockApplyProduction();
    const cost = qty * m.price;
    if (!mockCanAfford({ gold: cost })) throw new Error('طلای کافی نداری');
    mockPay({ gold: cost });
    mockAddResources({ [m.resource]: qty });
    m.qty -= qty;
    return { ok: true, resource: m.resource, qty, cost };
  },
  adminMarketList: () => mockMarket.map(m => ({ resource: m.resource, qty: m.qty, price: m.price, base_price: m.base_price })),
  adminMarketSet: (body) => {
    if (!TRADE_GOODS.includes(body.resource)) throw new Error('کالای نامعتبر');
    if (body.qty < 0 || body.price <= 0) throw new Error('مقدار یا قیمت نامعتبر');
    const existing = mockMarket.find(m => m.resource === body.resource);
    if (existing) Object.assign(existing, { qty: body.qty, price: body.price, prev_price: body.price, base_price: body.price });
    else mockMarket.push({ resource: body.resource, qty: body.qty, price: body.price, prev_price: body.price, base_price: body.price });
    return { ok: true };
  },
  adminMarketDelete: (resource) => {
    const i = mockMarket.findIndex(m => m.resource === resource);
    if (i === -1) throw new Error('این کالا توی بازار نیست');
    mockMarket.splice(i, 1);
    return { ok: true };
  },
  adminBlackMarketList: () => mockBlackMarket.map(m => ({
    id: m.id, resource: m.resource, qty: m.qty, price: m.price,
    expires_in_minutes: Math.max(0, Math.floor((m.expires_at - Date.now()) / 60000)),
  })),
  adminBlackMarketCreate: (body) => {
    if (!TRADE_GOODS.includes(body.resource)) throw new Error('کالای نامعتبر');
    if (body.qty <= 0 || body.price <= 0 || body.hours <= 0) throw new Error('مقدار، قیمت یا مدت نامعتبر');
    const id = `bm${mockBlackMarketSeq++}`;
    mockBlackMarket.push({ id, resource: body.resource, qty: body.qty, price: body.price, expires_at: Date.now() + body.hours * 3600000 });
    return { ok: true, id };
  },
  adminBlackMarketDelete: (id) => {
    const i = mockBlackMarket.findIndex(m => m.id === id);
    if (i === -1) throw new Error('این نشانی بازار سیاه پیدا نشد');
    mockBlackMarket.splice(i, 1);
    return { ok: true };
  },
  adminGetPlayerResources: (tgId) => {
    const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
    if (!p) throw new Error('بازیکن پیدا نشد');
    if (!mockPlayerResources[tgId]) mockPlayerResources[tgId] = { ...DEFAULT_MOCK_PLAYER_RESOURCES };
    return { name: p.name, castle: p.castle, points: p.points || 0, popularity: p.popularity ?? 50, resources: mockPlayerResources[tgId], resource_caps: { ...RESOURCE_CAPS } };
  },
  adminAdjustPlayerPoints: (tgId, delta) => {
    const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
    if (!p) throw new Error('بازیکن پیدا نشد');
    const old = p.points || 0;
    p.points = Math.max(0, old + Number(delta || 0));
    return { ok: true, old_points: old, points: p.points, applied_delta: p.points - old };
  },
  adminAdjustPlayerPopularity: (tgId, delta) => {
    const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
    if (!p) throw new Error('بازیکن پیدا نشد');
    const old = p.popularity ?? 50;
    p.popularity = Math.max(0, Math.min(100, old + Number(delta || 0)));
    return { ok: true, old_popularity: old, popularity: p.popularity, applied_delta: p.popularity - old };
  },
  adminSetPlayerResources: (tgId, resources) => {
    if (!mockPlayerResources[tgId]) mockPlayerResources[tgId] = { ...DEFAULT_MOCK_PLAYER_RESOURCES };
    for (const [k, v] of Object.entries(resources)) {
      const n = parseInt(v, 10);
      if (!Number.isFinite(n) || n < 0) throw new Error(`مقدار نامعتبر برای ${k}`);
      mockPlayerResources[tgId][k] = n;
    }
    return { ok: true };
  },
  adminCampaigns: () => {
    mockResolveCampaigns();
    const nowMs = Date.now();
    return mockCampaigns.slice().reverse().map(c => {
      const targetOwner = c.target_castle !== c.origin_castle
        ? MOCK_PLAYERS.find(p => p.castle === c.target_castle) : null;
      return {
        id: c.id, player: mockMe.name, tg_id: 1,
        from: c.origin_castle, to: c.target_castle,
        target_tg_id: targetOwner?.tg_id ?? null, target_player: targetOwner?.name ?? null,
        op_type: c.op_type, op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        name: c.name || OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        troops: Object.entries(c.troops || {}).filter(([, n]) => n > 0).map(([tid, n]) => ({
          name: mockTroopName(tid), count: n,
        })),
        gold_cost: c.gold_cost, men_committed: c.men_committed, food_per_day: c.food_per_day,
        travel_minutes: c.travel_minutes, arrived: nowMs >= new Date(c.arrival_at).getTime(),
        active: c.active, created_at: c.created_at,
      };
    });
  },
  adminPlayerCampaigns: (tgId) => {
    if (tgId !== 1) return []; // حالت آزمایشی تک‌بازیکنه — فقط لشکرهای خودت شبیه‌سازی می‌شود
    mockResolveCampaigns();
    return mockCampaigns.slice().reverse().map(c => ({
      id: c.id, name: c.name || OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
      op_name: OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
      from: c.origin_castle, to: c.target_castle,
      troops: Object.entries(c.troops || {}).filter(([, n]) => n > 0).map(([tid, n]) => ({
        name: mockTroopName(tid), count: n,
      })),
      power: c.power || 0, men_committed: c.men_committed,
      active: c.active, arrived: Date.now() >= new Date(c.arrival_at).getTime(),
    }));
  },
  adminDisbandCampaign: (id) => {
    const c = mockCampaigns.find(x => x.id === id);
    if (!c) throw new Error('این لشکرکشی پیدا نشد');
    if (!c.active) throw new Error('این لشکرکشی دیگر فعال نیست');
    c.active = false;
    mockAddResources({ men: c.men_committed });
    return { ok: true };
  },
  sendSpy: (targetCastle, scenario) => {
    mockResolveCampaigns();
    if (targetCastle === mockMe.castle) throw new Error('نمی‌توانی جاسوس به قلعهٔ خودت بفرستی');
    const targetPlayer = MOCK_PLAYERS.find(p => p.castle === targetCastle);
    if (!targetPlayer) throw new Error('این قلعه صاحبی ندارد که جاسوسی‌اش کنی');
    const s = (scenario || '').trim();
    if (s.length < 10) throw new Error('سناریوی جاسوسی خیلی کوتاه است — نقشه‌ات را کمی بیشتر توضیح بده');
    if (!mockCanAfford({ gold: SPY_GOLD_COST })) throw new Error('خزانه کافی نیست');
    if ((mockMe.resources.men ?? 0) < SPY_MEN_COST) throw new Error('نفرات کافی نداری');

    mockPay({ gold: SPY_GOLD_COST });
    mockMe.resources.men -= SPY_MEN_COST;

    const travel = spyTravelMinutes(mockMe.castle, targetCastle);

    const nowIso = new Date().toISOString();
    mockSpyMissions.push({
      id: String(mockSpySeq++), target: targetCastle, target_tg_id: targetPlayer.tg_id, scenario: s,
      men_sent: SPY_MEN_COST, travel_minutes: travel,
      arrival_at: new Date(Date.now() + travel * 60000).toISOString(),
      admin_score: null, resolved: false, success: null, report: null, created_at: nowIso,
    });
    return { ok: true, travel_minutes: travel };
  },
  spyMine: () => {
    const nowMs = Date.now();
    return mockSpyMissions.slice().reverse().map(m => ({
      id: m.id, target: m.target, scenario: m.scenario, travel_minutes: m.travel_minutes,
      arrived: nowMs >= new Date(m.arrival_at).getTime(),
      resolved: m.resolved,
      success: m.resolved ? m.success : null,
      report: (m.resolved && m.success) ? m.report : null,
      created_at: m.created_at,
    }));
  },
  adminSpyPending: () => mockSpyMissions.filter(m => !m.resolved).slice().reverse().map(m => ({
    id: m.id, player: mockMe.name || 'تو', tg_id: 1,
    origin: mockMe.castle, target: m.target, scenario: m.scenario,
    arrived: Date.now() >= new Date(m.arrival_at).getTime(), created_at: m.created_at,
  })),
  adminSpyResolved: () => mockSpyMissions.filter(m => m.resolved).slice().reverse().map(m => ({
    id: m.id, player: mockMe.name || 'تو', tg_id: 1,
    target: m.target, scenario: m.scenario,
    admin_score: m.admin_score, success: m.success, resolved_at: m.created_at,
  })),
  adminScoreSpy: (missionId, score) => {
    const m = mockSpyMissions.find(x => x.id === missionId);
    if (!m) throw new Error('این ماموریت پیدا نشد');
    if (m.resolved) throw new Error('این ماموریت قبلاً امتیازدهی شده');
    const sc = Math.max(0, Math.min(100, Math.round(score)));
    const success = Math.random() * 100 < sc;
    m.admin_score = sc; m.resolved = true; m.success = success;
    if (success) {
      const targetPlayer = MOCK_PLAYERS.find(p => p.castle === m.target);
      const seed = targetPlayer?.tg_id || 0;
      m.report = {
        resources: {
          gold: 400 + (seed % 600), food: 300 + (seed % 400),
          men: 200 + (seed % 300), wood: 80, stone: 60, iron: 40, wine: 10,
        },
        military: [{ name: 'پادگان پیاده‌نظام', level: 2 }],
        defense: [{ name: 'برج نگهبانی', level: 1 }],
        campaigns: [],
      };
      mockAddResources({ men: m.men_sent });
      mockSendSystemMessage(`جاسوس‌های تو با موفقیت به ${m.target} نفوذ کردند و گزارش کاملی به دست آوردند — نتیجه در بخش جاسوسی منتظر توست.`);
    } else {
      m.report = null;
      mockSendSystemMessage(`جاسوسی تو در ${m.target} شناسایی و دستگیر شد — نفرات اعزامی برنگشتند.`);
    }
    return { ok: true, success };
  },
  warRoleplayEligible: () => {
    mockResolveCampaigns();
    const nowMs = Date.now();
    const cutoff = nowMs - ROLEPLAY_WINDOW_HOURS * 3600000;
    const already = new Set(mockRoleplays.filter(r => r.category === 'war').map(r => r.campaign_id));
    return mockCampaigns
      .filter(c => ATTACK_OP_TYPES.includes(c.op_type))
      .filter(c => {
        const arrivalMs = new Date(c.arrival_at).getTime();
        return arrivalMs <= nowMs && arrivalMs >= cutoff;
      })
      .filter(c => !already.has(c.id))
      .map(c => ({
        campaign_id: c.id, role: 'attacker',
        name: c.name || OP_TYPES.find(o => o.id === c.op_type)?.name || c.op_type,
        origin: c.origin_castle, target: c.target_castle, arrival_at: c.arrival_at,
      }))
      .reverse();
  },
  sendRoleplay: (category, text, campaignId) => {
    if (!ROLEPLAY_CATEGORIES[category]) throw new Error('دسته‌بندی نامعتبر است');
    const t = (text || '').trim();
    if (t.length < 10) throw new Error('رول خیلی کوتاه است — کمی بیشتر بنویس');
    let campaign_id = null;
    if (category === 'war') {
      if (!campaignId) throw new Error('برای دستهٔ جنگ باید نبردت را انتخاب کنی');
      const c = mockCampaigns.find(x => x.id === campaignId);
      if (!c || !ATTACK_OP_TYPES.includes(c.op_type)) throw new Error('این نبرد پیدا نشد');
      const nowMs = Date.now();
      const arrivalMs = new Date(c.arrival_at).getTime();
      if (arrivalMs > nowMs) throw new Error('این نبرد هنوز به مقصد نرسیده');
      if (nowMs > arrivalMs + ROLEPLAY_WINDOW_HOURS * 3600000) throw new Error(`مهلت ${ROLEPLAY_WINDOW_HOURS} ساعته برای فرستادن سناریوی این نبرد گذشته`);
      if (mockRoleplays.some(r => r.category === 'war' && r.campaign_id === campaignId)) throw new Error('قبلاً سناریوی این نبرد را فرستاده‌ای');
      campaign_id = campaignId;
    }
    const result_required = category !== 'security';
    mockRoleplays.push({
      id: String(mockRoleplaySeq++), category, text: t, campaign_id,
      result: null, resolved: !result_required, result_required, created_at: new Date().toISOString(),
    });
    return { ok: true, result_required };
  },
  roleplayMine: () => mockRoleplays.slice().reverse().map(r => ({
    id: r.id, category: r.category, category_name: ROLEPLAY_CATEGORIES[r.category] || r.category,
    text: r.text, resolved: r.resolved, result: r.result, result_required: r.result_required !== false, campaign_id: r.campaign_id, created_at: r.created_at,
  })),
  adminRoleplayPending: () => mockRoleplays.filter(r => !r.resolved).slice().reverse().map(r => ({
    id: r.id, player: mockMe.name || 'تو', tg_id: 1, castle: mockMe.castle,
    category: r.category, category_name: ROLEPLAY_CATEGORIES[r.category] || r.category,
    text: r.text, campaign_id: r.campaign_id, sibling: null, created_at: r.created_at,
  })),
  adminRespondRoleplay: (roleplayId, result, visibility, otherLords = [], winnerTgId = null) => {
    const r = mockRoleplays.find(x => x.id === roleplayId);
    if (!r) throw new Error('این رول پیدا نشد');
    if (r.resolved) throw new Error('این رول قبلاً پاسخ داده شده');
    const res = (result || '').trim();
    if (res.length < 3) throw new Error('متن نتیجه خیلی کوتاه است');
    r.result = res; r.resolved = true;
    const catName = ROLEPLAY_CATEGORIES[r.category] || r.category;
    const prefix = visibility === 'all' ? 'اعلامیهٔ عمومی' : `نتیجهٔ رول «${catName}»`;
    mockSendSystemMessage(`${prefix}: ${res}`);
    if (visibility === 'all') return { ok: true, sent_to: MOCK_PLAYERS.length + 1 };
    const recipients = new Set([1, ...otherLords]);
    return { ok: true, sent_to: recipients.size };
  },
  leaderboard: () => [
    { rank: 1, name: 'دنریس تارگرین', castle: 'دراگون‌استون', region: 'کراون‌لندز', points: 2380 },
    { rank: 2, name: 'تایوین لنیستر', castle: 'کسترلی راک', region: 'وسترلندز', points: 2140 },
    { rank: 3, name: 'مارگری تایرل', castle: 'های‌گاردن', region: 'ریچ', points: 1990 },
    { rank: 4, name: mockMe.name || 'تو', castle: mockMe.castle || '—', region: mockMe.region_name || '—', points: 100, me: true },
  ],
  weeklyLeaderboard: () => [
    { rank: 1, name: 'مارگری تایرل', castle: 'های‌گاردن', region: 'ریچ', points: 340 },
    { rank: 2, name: 'دنریس تارگرین', castle: 'دراگون‌استون', region: 'کراون‌لندز', points: 295 },
    { rank: 3, name: 'تایوین لنیستر', castle: 'کسترلی راک', region: 'وسترلندز', points: 210 },
    { rank: 4, name: mockMe.name || 'تو', castle: mockMe.castle || '—', region: mockMe.region_name || '—', points: 40, me: true },
  ],
  dailyStatus: () => {
    const { streak, claimedToday } = dailyPendingStreak();
    const dayInCycle = dailyDayInCycle(streak);
    return {
      current_streak: mockDaily.streak, claimed_today: claimedToday,
      day_in_cycle: dayInCycle, cycle_length: DAILY_REWARDS.length,
      reward: DAILY_REWARDS[dayInCycle - 1],
    };
  },
  dailyClaim: () => {
    if (!mockMe.resources) throw new Error('اول باید خاندان و قلعه‌ات تعیین شده باشد');
    const { streak, claimedToday } = dailyPendingStreak();
    if (claimedToday) throw new Error('امروز جایزه‌ات را گرفته‌ای — فردا دوباره سر بزن');
    const dayInCycle = dailyDayInCycle(streak);
    const reward = DAILY_REWARDS[dayInCycle - 1];
    mockAddResources(reward);
    mockDaily.streak = streak; mockDaily.lastClaimDate = dailyTodayStr();
    return { ok: true, streak, day_in_cycle: dayInCycle, reward, resources: mockMe.resources };
  },
  ravensUnread: () => {
    const announcements = mockMessages.filter(m => m.to_id === 1 && m.from_id === 0 && !m.read).length;
    const personal = mockMessages.filter(m => m.to_id === 1 && m.from_id !== 0 && !m.read).length;
    const rumorCount = mockRumors.filter(r => r.author_tg_id !== 1 && new Date(r.created_at).getTime() > mockRumorsSeenAt).length;
    return { count: announcements + personal + rumorCount, announcements, messages: personal, rumors: rumorCount };
  },
  inbox: () => {
    const convos = {};
    for (const m of mockMessages) {
      const otherId = m.from_id === 1 ? m.to_id : m.from_id;
      const otherName = m.from_id === 1 ? m.to_name : m.from_name;
      if (!convos[otherId] || new Date(m.created_at) > new Date(convos[otherId].last_at)) {
        convos[otherId] = { with_tg_id: otherId, with_name: otherName, last_text: m.text, last_at: m.created_at, unread: 0 };
      }
    }
    for (const m of mockMessages) {
      if (m.to_id === 1 && !m.read) {
        const c = convos[m.from_id];
        if (c) c.unread++;
      }
    }
    return Object.values(convos).sort((a, b) => new Date(b.last_at) - new Date(a.last_at));
  },
  thread: (otherTgId) => {
    const relevant = mockMessages.filter(m =>
      (m.from_id === 1 && m.to_id === otherTgId) || (m.to_id === 1 && m.from_id === otherTgId)
    );
    relevant.forEach(m => { if (m.to_id === 1 && m.from_id === otherTgId) m.read = true; });
    return relevant.slice()
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
      .map(m => ({ mine: m.from_id === 1, text: m.text }));
  },
  buildings: (castle) => {
    mockResolve();
    const targetCastle = castle && mockOwnedCastles().includes(castle) ? castle : mockMe.castle;
    const state = mockCastleBuildingState(targetCastle);
    const isPort = mockCastleTerrain(targetCastle) !== 'land';
    const rows = Object.entries(BUILDINGS_STATIC).map(([id, meta]) => {
      const st = state[id] || { level: 0, upgrade_to: null, ready_at: null };
      const next = st.upgrade_to || (st.level < MAX_BUILDING_LEVEL ? st.level + 1 : null);
      const perLevelProduces = buildingProduces(id);
      const perLevelCap = buildingCapBonus(id);
      return {
        id, name: meta.name, type: meta.type, unit: meta.unit, requires_port: !!meta.requires_port,
        level: st.level, max_level: MAX_BUILDING_LEVEL,
        upgrading: !!st.upgrade_to, ready_at: st.ready_at,
        next_level: next,
        next_cost: next ? buildingCost(id, next) : null,
        next_hours: next ? buildingHours(id, next) : null,
        produces_per_level: perLevelProduces,
        current_yield: st.level ? Object.fromEntries(Object.entries(perLevelProduces).map(([k, v]) => [k, v * st.level])) : {},
        cap_bonus_per_level: perLevelCap,
        current_cap_bonus: st.level ? Object.fromEntries(Object.entries(perLevelCap).map(([k, v]) => [k, v * st.level])) : {},
      };
    });
    return { castle: targetCastle, is_port: isPort, castles: mockOwnedCastles(), buildings: rows };
  },
  buildAction: (id, requireBuilt, castle) => {
    mockResolve();
    mockApplyProduction();
    const targetCastle = castle && mockOwnedCastles().includes(castle) ? castle : mockMe.castle;
    const state = mockCastleBuildingState(targetCastle);
    const isPort = mockCastleTerrain(targetCastle) !== 'land';
    const st = state[id] || { level: 0, upgrade_to: null, ready_at: null };
    if (st.upgrade_to) throw new Error('این ساختمان هم‌اکنون در حال ساخت است');
    if (requireBuilt && st.level === 0) throw new Error('اول این ساختمان را بنا کن');
    if (!requireBuilt && st.level > 0) throw new Error('این ساختمان قبلاً بنا شده — آن را ارتقا بده');
    if (st.level >= MAX_BUILDING_LEVEL) throw new Error('این ساختمان به بیشینهٔ سطح رسیده');
    if (!requireBuilt && BUILDINGS_STATIC[id]?.requires_port && !isPort) {
      throw new Error('این ساختمان فقط در قلعه/شهرهای دریایی و بندری ساخته می‌شود');
    }
    const target = st.level + 1;
    const cost = buildingCost(id, target);
    if (!mockCanAfford(cost)) throw new Error('منابع کافی نیست');
    mockPay(cost);
    st.upgrade_to = target;
    st.ready_at = new Date(Date.now() + buildingHours(id, target) * 3600 * 1000).toISOString();
    state[id] = st;
    return { ok: true, target_level: target, cost, ready_at: st.ready_at };
  },
  myCastles: () => mockOwnedCastles().map(c => ({
    name: c, home: c === mockMe.castle, house: CASTLE_HOUSES[c] || null,
    is_port: mockCastleTerrain(c) !== 'land',
  })),
  castleAssets: (castle) => {
    mockResolve();
    const targetCastle = castle && mockOwnedCastles().includes(castle) ? castle : mockMe.castle;
    return Object.entries(mockCastleBuildingState(targetCastle))
      .filter(([, st]) => st.level > 0)
      .map(([id, st]) => {
        const meta = BUILDINGS_STATIC[id];
        const { produces, cap_bonus } = buildingYield(id, st.level);
        return { id, name: meta.name, type: meta.type, level: st.level, produces, cap_bonus };
      })
      .sort((a, b) => b.level - a.level || a.name.localeCompare(b.name, 'fa'));
  },
  myItems: () => {
    const nowMs = Date.now();
    return mockItemGrants
      .filter(g => g.tg_id === 1)
      .filter(g => !g.expires_at || new Date(g.expires_at).getTime() > nowMs)
      .slice().reverse()
      .map(g => {
        const tpl = mockItems.find(t => t.id === g.item_id);
        if (!tpl) return null;
        return {
          id: g.id, item_id: tpl.id, name: tpl.name,
          type: tpl.type, type_name: ITEM_TYPES[tpl.type] || tpl.type,
          description: tpl.description || '',
          duration: tpl.duration, duration_name: ITEM_DURATIONS[tpl.duration] || tpl.duration,
          color: g.color, color_name: ITEM_RARITY_COLORS[g.color] || g.color,
          granted_at: g.granted_at, expires_at: g.expires_at,
        };
      })
      .filter(Boolean);
  },
  adminListItems: () => {
    return mockItems.slice().reverse().map(tpl => ({
      id: tpl.id, name: tpl.name,
      type: tpl.type, type_name: ITEM_TYPES[tpl.type] || tpl.type,
      duration: tpl.duration, duration_name: ITEM_DURATIONS[tpl.duration] || tpl.duration,
      duration_hours: tpl.duration_hours, description: tpl.description || '',
      grant_count: mockItemGrants.filter(g => g.item_id === tpl.id).length,
    }));
  },
  adminCreateItem: (body) => {
    const name = (body.name || '').trim();
    if (!name) throw new Error('نام آیتم را بنویس');
    if (!ITEM_TYPES[body.type]) throw new Error('نوع آیتم نامعتبر');
    if (!ITEM_DURATIONS[body.duration]) throw new Error('مدت آیتم نامعتبر');
    let durationHours = null;
    if (body.duration === 'temporary') {
      durationHours = parseInt(body.duration_hours, 10);
      if (!durationHours || durationHours <= 0) throw new Error('برای آیتم موقتی، مدت (ساعت) را مشخص کن');
    }
    const doc = {
      id: String(mockItemSeq++), name: name.slice(0, 60), type: body.type, duration: body.duration,
      duration_hours: durationHours, description: (body.description || '').trim().slice(0, 300),
      created_at: new Date().toISOString(),
    };
    mockItems.push(doc);
    return { ok: true, id: doc.id };
  },
  adminDeleteItem: (itemId) => {
    const i = mockItems.findIndex(t => t.id === itemId);
    if (i === -1) throw new Error('این آیتم پیدا نشد');
    mockItems.splice(i, 1);
    for (let j = mockItemGrants.length - 1; j >= 0; j--) {
      if (mockItemGrants[j].item_id === itemId) mockItemGrants.splice(j, 1);
    }
    return { ok: true };
  },
  adminGetBuildingBalance: () => {
    return Object.entries(BUILDINGS_STATIC)
      .map(([id, meta]) => ({
        id, name: meta.name, type: meta.type,
        base_cost: meta.cost || {}, cost: BUILDING_OVERRIDES[id]?.cost || meta.cost || {},
        base_cost_step_percent: 15, cost_step_percent: (BUILDING_OVERRIDES[id]?.cost_step ?? .15) * 100,
        base_hours: meta.hours, hours: BUILDING_OVERRIDES[id]?.hours ?? meta.hours,
        base_max_level: meta.max_level || MAX_BUILDING_LEVEL, max_level: BUILDING_OVERRIDES[id]?.max_level || meta.max_level || MAX_BUILDING_LEVEL,
        base_produces: meta.produces || {}, base_cap_bonus: meta.cap_bonus || {},
        overridden: !!BUILDING_OVERRIDES[id],
        produces: buildingProduces(id), cap_bonus: buildingCapBonus(id),
      }));
  },
  adminSetBuildingBalance: (body) => {
    const meta = BUILDINGS_STATIC[body.building_id];
    if (!meta) throw new Error('ساختمان نامعتبر');
    const allowedProduces = Object.keys(meta.produces || {});
    const allowedCap = Object.keys(meta.cap_bonus || {});
    const produces = body.produces || {};
    const capBonus = body.cap_bonus || {};
    if (Object.keys(produces).some(k => !allowedProduces.includes(k)) || Object.keys(capBonus).some(k => !allowedCap.includes(k))) {
      throw new Error('این ساختمان چنین منبعی تولید/ذخیره نمی‌کند');
    }
    if ([...Object.values(produces), ...Object.values(capBonus)].some(v => v < 0)) throw new Error('مقدار نمی‌تواند منفی باشد');
    const override = { cost: body.cost || meta.cost || {}, cost_step: Number(body.cost_step_percent || 0) / 100, hours: Number(body.hours), max_level: Number(body.max_level) };
    if (Object.keys(produces).length) override.produces = produces;
    if (Object.keys(capBonus).length) override.cap_bonus = capBonus;
    if (Object.keys(override).length) BUILDING_OVERRIDES[body.building_id] = override;
    else delete BUILDING_OVERRIDES[body.building_id];
    return { ok: true };
  },
  adminResetBuildingBalance: (id) => {
    delete BUILDING_OVERRIDES[id];
    return { ok: true };
  },
  adminGetGameplayBalance: () => ({
    rules: { camp_power_step_percent: CAMP_POWER_STEP * 100, special_troop_cost: SPECIAL_COST, special_troop_power: SPECIAL_POWER, food_cost_regular: FOOD_COST_REGULAR, food_cost_special: FOOD_COST_SPECIAL, weapon_per_soldier: WEAPON_PER_SOLDIER, level_hours_step_percent: 6, default_max_building_level: MAX_BUILDING_LEVEL, equipment_slowdown_cap_percent: 100, commander_power_bonus_percent: 10, commander_speed_bonus_percent: 5 },
    common_troops: COMMON_TROOPS.map(t => ({ ...t })),
    naval_troops: NAVAL_TROOPS.map(t => ({ ...t })),
    equipment: SIEGE_EQUIPMENT.map(e => ({ ...e, cost: { ...e.cost }, slowdown_percent: e.slowdown * 100 })),
  }),
  adminSetGameplayBalance: (body) => body,
  adminResetGameplayBalance: () => M.adminGetGameplayBalance(),
  adminGrantItem: (itemId, tgId, color) => {
    const tpl = mockItems.find(t => t.id === itemId);
    if (!tpl) throw new Error('این آیتم پیدا نشد');
    if (!ITEM_RARITY_COLORS[color]) throw new Error('رنگ نامعتبر');
    const target = tgId === 1 ? { tg_id: 1, name: mockMe.name } : MOCK_PLAYERS.find(p => p.tg_id === tgId);
    if (!target) throw new Error('این لرد پیدا نشد');
    const expiresAt = tpl.duration === 'temporary'
      ? new Date(Date.now() + tpl.duration_hours * 3600 * 1000).toISOString() : null;
    mockItemGrants.push({
      id: String(mockItemGrantSeq++), item_id: itemId, tg_id: tgId, color,
      granted_at: new Date().toISOString(), expires_at: expiresAt,
    });
    return { ok: true };
  },
  sendRumor: (targetTgId, text) => {
    if (targetTgId === 1) throw new Error('نمی‌توانی علیه خودت توییت بسازی');
    const t = text.trim();
    if (t.length < 10) throw new Error('متن توییت خیلی کوتاه است');
    const target = MOCK_PLAYERS.find(p => p.tg_id === targetTgId);
    if (!target) throw new Error('این لرد پیدا نشد');
    const nowMs = Date.now();
    const recent = mockRumors.find(r => r.author_tg_id === 1 && r.target_tg_id === targetTgId
      && nowMs - new Date(r.created_at).getTime() < RUMOR_COOLDOWN_HOURS * 3600000);
    if (recent) throw new Error(`همین الان علیه این لرد توییت ساختی — ${RUMOR_COOLDOWN_HOURS} ساعت دیگر دوباره امتحان کن`);
    if (!mockCanAfford({ gold: RUMOR_GOLD_COST })) throw new Error('طلای کافی برای پخش این توییت نداری');
    mockPay({ gold: RUMOR_GOLD_COST });
    target.popularity = Math.max(0, (target.popularity ?? 50) - RUMOR_POPULARITY_DAMAGE);
    mockRumors.unshift({
      id: String(mockRumorSeq++), author_tg_id: 1, author_name: mockMe.name,
      target_tg_id: targetTgId, target_name: target.name,
      text: t.slice(0, 400), created_at: new Date().toISOString(), reactions: {},
    });
    return { ok: true };
  },
  listRumors: () => mockRumors.map(r => rumorBrief(r)),
  markRumorsSeen: () => { mockRumorsSeenAt = Date.now(); return { ok: true }; },
  reactRumor: (rumorId, reaction) => {
    const r = mockRumors.find(x => x.id === rumorId);
    if (!r) throw new Error('این توییت پیدا نشد');
    if (r.author_tg_id === 1) throw new Error('نمی‌توانی به توییتٔ خودت واکنش نشان بدهی');
    if (!['like', 'dislike', null].includes(reaction)) throw new Error('واکنش نامعتبر');
    if (reaction === null) delete r.reactions[1];
    else r.reactions[1] = reaction;
    return rumorBrief(r);
  },
  titles: () => {
    const brief = (p) => p ? { tg_id: p.tg_id, name: p.name, title: p.title, castle: p.castle } : null;
    const meBrief = { tg_id: 1, name: mockMe.name, title: mockMe.title, castle: mockMe.castle };
    const isKing = mockHierarchy.king_tg_id === 1;
    const councilHolders = {};
    for (const seat of Object.keys(SMALL_COUNCIL_SEATS)) {
      const tgId = mockHierarchy.small_council[seat];
      councilHolders[seat] = tgId ? brief(MOCK_PLAYERS.find(x => x.tg_id === tgId)) : null;
    }
    return {
      overlords: Object.fromEntries(Object.keys(REGIONS_STATIC).map(id => [id, null])),
      warden_groups: WARDEN_GROUPS,
      wardens: { south: null, central: null, north: null },
      king: isKing ? meBrief : null,
      small_council_seats: SMALL_COUNCIL_SEATS,
      small_council: councilHolders,
      is_king: isKing,
      treasury_gold: mockHierarchy.treasury_gold,
      council_salary_rates: mockHierarchy.council_salary_rates,
      king_salary_gold: mockHierarchy.king_salary_rate,
    };
  },
  setSmallCouncil: (seat, tgId) => {
    if (!SMALL_COUNCIL_SEATS[seat]) throw new Error('کرسی نامعتبر');
    if (tgId == null) { delete mockHierarchy.small_council[seat]; return { ok: true }; }
    if (tgId === 1) throw new Error('پادشاه/ملکه نمی‌تواند خودش را عضو شورای کوچک کند');
    if (!MOCK_PLAYERS.find(x => x.tg_id === tgId)) throw new Error('لرد پیدا نشد');
    mockHierarchy.small_council[seat] = tgId;
    return { ok: true };
  },
  setCouncilSalary: (seat, amount) => {
    if (mockHierarchy.king_tg_id !== 1) throw new Error('فقط پادشاه/ملکهٔ فعلی می‌تواند حقوقِ شورای کوچک را تعیین کند');
    if (!SMALL_COUNCIL_SEATS[seat]) throw new Error('کرسی نامعتبر');
    if (amount < 0) throw new Error('حقوق نمی‌تواند منفی باشد');
    mockHierarchy.council_salary_rates[seat] = amount;
    return { ok: true };
  },
  setKingSalary: (amount) => {
    if (mockHierarchy.king_tg_id !== 1) throw new Error('فقط پادشاه/ملکهٔ فعلی می‌تواند حقوقِ خودش را تعیین کند');
    if (amount < 0) throw new Error('حقوق نمی‌تواند منفی باشد');
    mockHierarchy.king_salary_rate = amount;
    return { ok: true };
  },
  tributeMine: () => {
    const { role, targets } = mockMyTributeRole(1);
    const demandTargets = [...targets].map(tgId => {
      if (tgId === 1) return { tg_id: 1, name: mockMe.name, title: mockMe.title };
      const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
      return p ? { tg_id: p.tg_id, name: p.name, title: p.title } : null;
    }).filter(Boolean);
    const demanded = mockTributes.filter(t => t.from_id === 1).map(t => ({
      id: t.id, to_name: t.to_name, amount: t.amount, status: t.status,
      created_at: t.created_at, due_at: t.due_at,
    }));
    const owed = mockTributes.filter(t => t.to_id === 1 && t.status === 'pending').map(t => ({
      id: t.id, from_name: t.from_name, from_role: t.from_role, from_role_label: ROLE_LABEL_FA[t.from_role],
      amount: t.amount, created_at: t.created_at, due_at: t.due_at,
    }));
    return {
      my_role: role, my_role_label: role ? ROLE_LABEL_FA[role] : null,
      demand_targets: demandTargets, demanded, owed,
    };
  },
  demandTribute: (toTgId, amount) => {
    if (!(amount > 0)) throw new Error('مبلغ باید مثبت باشد');
    const { role, targets } = mockMyTributeRole(1);
    if (!role) throw new Error('مقامی نداری که بتونی خراج بخوای');
    if (!targets.has(toTgId)) throw new Error('این بازیکن زیردستِ مستقیمِ تو نیست');
    if (mockTributes.some(t => t.from_id === 1 && t.to_id === toTgId && t.status === 'pending')) {
      throw new Error('همین الان یک خراجِ پرداخت‌نشده از این نفر خواسته‌ای — صبر کن جواب بده');
    }
    const target = toTgId === 1 ? { name: mockMe.name } : MOCK_PLAYERS.find(x => x.tg_id === toTgId);
    if (!target) throw new Error('این بازیکن پیدا نشد');
    const createdAt = new Date();
    const dueAt = new Date(createdAt.getTime() + 24 * 3600000);
    const doc = {
      id: String(mockTributeSeq++), from_id: 1, from_name: mockMe.name, from_role: role,
      to_id: toTgId, to_name: target.name, amount, status: 'pending',
      created_at: createdAt.toISOString(), due_at: dueAt.toISOString(), paid_at: null,
    };
    mockTributes.push(doc);
    return { ok: true, id: doc.id };
  },
  payTribute: (id) => {
    const t = mockTributes.find(x => x.id === id);
    if (!t) throw new Error('این خراج پیدا نشد');
    if (t.to_id !== 1) throw new Error('این خراجِ تو نیست');
    if (t.status !== 'pending') throw new Error('این خراج دیگر در انتظار پرداخت نیست');
    if (!mockCanAfford({ gold: t.amount })) throw new Error('طلای کافی نداری');
    mockPay({ gold: t.amount });
    t.status = 'paid'; t.paid_at = new Date().toISOString();
    mockSendSystemMessage(`${mockMe.name} خراجِ ${t.amount.toLocaleString('fa-IR')} سکه‌ای که خواسته بودی را پرداخت کرد.`);
    return { ok: true };
  },
  diplomacyMine: () => mockAlliances,
  diplomacyPublic: () => mockAlliances
    .filter(a => a.status === 'accepted' && a.public !== false)
    .map(a => ({
      id: a.id, type: a.type, type_name: a.type_name, name: a.name || '',
      from_name: a.mine_proposed ? mockMe.name : a.other_name,
      to_name: a.mine_proposed ? a.other_name : mockMe.name,
    })),
  diplomacyPropose: (toTgIds, type, name, isPrivate, penaltyGold) => {
    if (!ALLIANCE_TYPES[type]) throw new Error('نوع پیمان نامعتبر');
    if (!toTgIds.length) throw new Error('هیچ گیرنده‌ای انتخاب نشده');
    if (type === 'non_aggression' && !(penaltyGold > 0)) throw new Error('برای پیمان عدم‌تجاوز باید مقدار غرامت (طلا) را مشخص کنی');
    const unitCost = ALLIANCE_TYPES[type].wine_cost * (isPrivate ? PRIVATE_ALLIANCE_MULTIPLIER : 1);
    const cost = unitCost * toTgIds.length;
    if (!mockCanAfford({ wine: cost })) throw new Error(`شراب کافی برای پیشنهاد به ${toTgIds.length} نفر نداری`);
    mockPay({ wine: cost });
    const pactName = (name || '').trim().slice(0, 60);
    for (const tgId of toTgIds) {
      const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
      mockAlliances.unshift({
        id: String(mockAllianceSeq++), mine_proposed: true, other_id: tgId, other_name: p ? p.name : String(tgId),
        type, type_name: ALLIANCE_TYPES[type].name, name: pactName, public: !isPrivate,
        wine_cost: unitCost, penalty_gold: type === 'non_aggression' ? penaltyGold : 0, status: 'pending',
      });
    }
    return { ok: true, sent_to: toTgIds.length };
  },
  diplomacyRespond: (id, accept) => {
    const a = mockAlliances.find(x => x.id === id);
    if (!a) throw new Error('پیمان پیدا نشد');
    a.status = accept ? 'accepted' : 'rejected';
    if (accept) mockMe.alliance_count = (mockMe.alliance_count ?? 0) + 1;
    else mockAddResources({ wine: a.wine_cost || 0 });
    return { ok: true };
  },
  diplomacyLeave: (id) => {
    const a = mockAlliances.find(x => x.id === id);
    if (!a) throw new Error('پیمان پیدا نشد');
    if (a.type !== 'trade') throw new Error('فقط از پیمان تجاری می‌شود خودت خارج شد');
    if (a.status !== 'accepted') throw new Error('فقط پیمان برقرار را می‌شود ترک کرد');
    a.status = 'left';
    mockMe.alliance_count = Math.max(0, (mockMe.alliance_count ?? 0) - 1);
    return { ok: true };
  },
  adminListAlliances: () => mockAlliances.map(a => ({
    id: a.id,
    from: a.mine_proposed ? (mockMe.name || 'تو') : a.other_name,
    to: a.mine_proposed ? a.other_name : (mockMe.name || 'تو'),
    type: a.type, type_name: a.type_name, name: a.name || '',
    status: a.status, public: a.public !== false,
  })),
  adminDissolveAlliance: (id) => {
    const a = mockAlliances.find(x => x.id === id);
    if (!a) throw new Error('این پیمان پیدا نشد');
    if (a.status !== 'accepted') throw new Error('فقط پیمان برقرار را می‌شود منحل کرد');
    a.status = 'dissolved';
    mockMe.alliance_count = Math.max(0, (mockMe.alliance_count ?? 0) - 1);
    mockSendSystemMessage(`پیمانت با لرد ${a.other_name} به فرمان ادمین منحل شد.`);
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
    const t = text.trim();
    if (!t) throw new Error('نامه خالی است');
    for (const tgId of toTgIds) {
      const p = MOCK_PLAYERS.find(x => x.tg_id === tgId);
      mockMessages.push({
        from_id: 1, to_id: tgId, from_name: mockMe.name || 'تو', to_name: p ? p.name : String(tgId),
        text: t, read: true, created_at: new Date().toISOString(),
      });
    }
    return { ok: true, sent_to: toTgIds.length };
  },
  // مقام‌ها/رای‌گیری در حالت mock پیاده نشده — این اپ دمو تک‌بازیکنه و پنل ادمین کامل به بک‌اند واقعی نیاز دارد
  adminSetOverlord: () => ({ ok: true }),
  adminSetWarden: () => ({ ok: true }),
  adminSetKing: () => ({ ok: true }),
  adminSetEpithet: () => ({ ok: true }),
  adminCreatePoll: () => ({ ok: true }),
  adminClosePoll: () => ({ ok: true }),
  adminDeletePoll: () => ({ ok: true }),
  adminListAdmins: () => [],
  adminAddAdmin: () => ({ ok: true }),
  adminRemoveAdmin: () => ({ ok: true }),
  adminResetGamePreview: () => ({ total_players: 1, non_admin_players: 0, admins_kept: 1 }),
  adminResetGame: (confirm) => {
    if (confirm !== 'RESET') throw new Error('برای تایید، دقیقاً عبارت RESET را تایپ کن');
    // حالت آزمایشی تک‌بازیکنه — «خودت» همیشه ادمینی، پس کسی حذف نمی‌شود؛
    // فقط تاریخچه‌ها مثل نسخهٔ واقعی پاک می‌شوند تا رفتار دکمه قابل‌آزمایش باشد
    mockCampaigns.length = 0;
    mockCaravans.length = 0;
    mockSpyMissions.length = 0;
    mockRoleplays.length = 0;
    mockRumors.length = 0;
    mockAlliances.length = 0;
    mockPolls.length = 0;
    mockMe.alliance_count = 0;
    return { ok: true, players_deleted: 0 };
  },
};

/* ---------- API عمومی ---------- */
// در حالت MOCK نتیجه با Promise.resolve بسته‌بندی می‌شود تا امضای async با حالت واقعی یکی بماند
export const api = {
  gamedata: () => MOCK ? Promise.resolve(null) : req('/api/gamedata'),
  gamedata:  () => MOCK ? Promise.resolve(M.gamedata) : req('/api/gamedata'),
  me:        () => MOCK ? Promise.resolve(M.me()) : req('/api/players/me'),
  musicSettings: () => MOCK ? Promise.resolve({ enabled: false, title: 'موسیقی والریا', audio_url: '', volume: 35, loop: true, autoplay: true }) : req('/api/players/music'),
  adminMusicSettings: () => MOCK ? Promise.resolve({ enabled: false, title: 'موسیقی والریا', audio_url: '', volume: 35, loop: true, autoplay: true }) : req('/api/admin/music'),
  adminSaveMusicSettings: (settings) => MOCK ? Promise.resolve(settings) : req('/api/admin/music', { method: 'POST', body: JSON.stringify(settings) }),
  register:  (b) => MOCK ? Promise.resolve(M.register(b)) : req('/api/players/register', { method: 'POST', body: JSON.stringify(b) }),
  map:       () => MOCK ? Promise.resolve(M.map()) : req(`/api/map?_=${Date.now()}`, { cache: 'no-store' }),
  warMine:   () => MOCK ? Promise.resolve(M.warMine()) : req('/api/war/mine'),
  legions:   () => MOCK ? Promise.resolve(M.legions()) : req('/api/war/legions'),
  warWindow: () => MOCK ? Promise.resolve(M.warWindow()) : req('/api/war/window'),
  adminGetWarWindow: () => MOCK ? Promise.resolve(M.adminGetWarWindow()) : req('/api/admin/war-window'),
  adminSetWarWindow: (open) => MOCK ? Promise.resolve(M.adminSetWarWindow(open)) : req('/api/admin/war-window', { method: 'POST', body: JSON.stringify({ open }) }),
  adminAnnounceEvent: (title, description, imageUrl = null) => MOCK ? Promise.resolve(M.adminAnnounceEvent(title, description))
    : req('/api/admin/announce-event', { method: 'POST', body: JSON.stringify({ title, description, image_url: imageUrl }) }),
  adminAwardStoryteller: (tgId, tier, reason = '') => MOCK ? Promise.resolve(M.adminAwardStoryteller(tgId, tier, reason))
    : req(`/api/admin/players/${tgId}/medals/realm-storyteller`, { method: 'POST', body: JSON.stringify({ tier, reason }) }),
  adminAwardSpecialMedal: (tgId, medal) => MOCK ? Promise.resolve(M.adminAwardSpecialMedal(tgId, medal))
    : req(`/api/admin/players/${tgId}/medals/special`, { method: 'POST', body: JSON.stringify(medal) }),
  adminSendBotMessage: (text, sendToAll, toTgIds = [], viaBot = true, viaRaven = false, imageUrl = null) => MOCK ? Promise.resolve(M.adminSendBotMessage(text, sendToAll, toTgIds))
    : req('/api/admin/send-bot-message', { method: 'POST', body: JSON.stringify({ text, send_to_all: sendToAll, to_tg_ids: toTgIds, via_bot: viaBot, via_raven: viaRaven, image_url: imageUrl }) }),
  submitCampaign: (b) => MOCK ? Promise.resolve(M.submitCampaign(b)) : req('/api/war/submit', { method: 'POST', body: JSON.stringify(b) }),
  warRoutes: (origin, target) => MOCK ? Promise.resolve(M.warRoutes(origin, target))
    : req(`/api/war/routes?origin_castle=${encodeURIComponent(origin)}&target_castle=${encodeURIComponent(target)}`),
  cancelCampaign: (id) => MOCK ? Promise.resolve(M.cancelCampaign(id)) : req(`/api/war/${id}/cancel`, { method: 'POST' }),
  moveCampaign: (id, b) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/war/${id}/move`, { method: 'POST', body: JSON.stringify(b) }),
  orderSiegeAttack: (id) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/war/${id}/attack`, { method: 'POST' }),
  ambushOptions: () => MOCK ? Promise.resolve([]) : req('/api/war/ambush/options'),
  myAmbushes: () => MOCK ? Promise.resolve([]) : req('/api/war/ambush/mine'),
  createAmbush: (b) => MOCK ? Promise.resolve({ ok: true }) : req('/api/war/ambush', { method: 'POST', body: JSON.stringify(b) }),
  adminMapOptions: (region) => MOCK ? Promise.resolve(M.adminMapOptions(region)) : req('/api/admin/map/options?region=' + encodeURIComponent(region)),
  adminAddMapCastle: (b) => MOCK ? Promise.resolve(M.adminAddMapCastle(b)) : req('/api/admin/map/castles', { method: 'POST', body: JSON.stringify(b) }),
  adminDeleteMapCastle: (name) => MOCK ? Promise.resolve(M.adminDeleteMapCastle(name))
    : req(`/api/admin/map/castles/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  adminEditMapCastle: (name, b) => MOCK ? Promise.resolve(M.adminEditMapCastle(name, b))
    : req(`/api/admin/map/castles/${encodeURIComponent(name)}`, { method: 'PATCH', body: JSON.stringify(b) }),
  sendCaravan: (b) => MOCK ? Promise.resolve(M.sendCaravan(b)) : req('/api/trade/caravan', { method: 'POST', body: JSON.stringify(b) }),
  playerCastles: (tgId) => MOCK ? Promise.resolve(M.playerCastles(tgId)) : req(`/api/players/${tgId}/castles`),
  myCaravans: () => MOCK ? Promise.resolve(M.myCaravans()) : req('/api/trade/caravans/mine'),
  market: () => MOCK ? Promise.resolve(M.market()) : req('/api/market'),
  marketBuy: (resource, qty) => MOCK ? Promise.resolve(M.marketBuy(resource, qty))
    : req('/api/market/buy', { method: 'POST', body: JSON.stringify({ resource, qty }) }),
  playerMarket: () => MOCK ? Promise.resolve([]) : req('/api/market/players'),
  playerMarketSell: (resource, qty) => MOCK ? Promise.resolve({ ok: true })
    : req('/api/market/players', { method: 'POST', body: JSON.stringify({ resource, qty }) }),
  playerMarketBuy: (listingId, qty) => MOCK ? Promise.resolve({ ok: true })
    : req('/api/market/players/buy', { method: 'POST', body: JSON.stringify({ listing_id: listingId, qty }) }),
  playerMarketCancel: (listingId) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/market/players/${encodeURIComponent(listingId)}`, { method: 'DELETE' }),
  blackMarket: () => MOCK ? Promise.resolve(M.blackMarket()) : req('/api/market/black'),
  blackMarketBuy: (listingId, qty) => MOCK ? Promise.resolve(M.blackMarketBuy(listingId, qty))
    : req('/api/market/black/buy', { method: 'POST', body: JSON.stringify({ listing_id: listingId, qty }) }),
  adminMarketList: () => MOCK ? Promise.resolve(M.adminMarketList()) : req('/api/admin/market'),
  adminMarketSet: (b) => MOCK ? Promise.resolve(M.adminMarketSet(b)) : req('/api/admin/market', { method: 'POST', body: JSON.stringify(b) }),
  adminMarketDelete: (resource) => MOCK ? Promise.resolve(M.adminMarketDelete(resource))
    : req(`/api/admin/market/${encodeURIComponent(resource)}`, { method: 'DELETE' }),
  adminBlackMarketList: () => MOCK ? Promise.resolve(M.adminBlackMarketList()) : req('/api/admin/market/black'),
  adminBlackMarketCreate: (b) => MOCK ? Promise.resolve(M.adminBlackMarketCreate(b))
    : req('/api/admin/market/black', { method: 'POST', body: JSON.stringify(b) }),
  adminBlackMarketDelete: (id) => MOCK ? Promise.resolve(M.adminBlackMarketDelete(id))
    : req(`/api/admin/market/black/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  adminGetPlayerResources: (tgId) => MOCK ? Promise.resolve(M.adminGetPlayerResources(tgId)) : req(`/api/admin/players/${tgId}/resources`),
  adminSetPlayerResources: (tgId, resources) => MOCK ? Promise.resolve(M.adminSetPlayerResources(tgId, resources))
    : req(`/api/admin/players/${tgId}/resources`, { method: 'POST', body: JSON.stringify({ resources }) }),
  adminAdjustPlayerPoints: (tgId, delta) => MOCK ? Promise.resolve(M.adminAdjustPlayerPoints(tgId, delta))
    : req(`/api/admin/players/${tgId}/points`, { method: 'POST', body: JSON.stringify({ delta }) }),
  adminAdjustPlayerPopularity: (tgId, delta) => MOCK ? Promise.resolve(M.adminAdjustPlayerPopularity(tgId, delta))
    : req(`/api/admin/players/${tgId}/popularity`, { method: 'POST', body: JSON.stringify({ delta }) }),
  leaderboard: () => MOCK ? Promise.resolve(M.leaderboard()) : req('/api/leaderboard'),
  weeklyLeaderboard: () => MOCK ? Promise.resolve(M.weeklyLeaderboard()) : req('/api/leaderboard/weekly'),
  dailyStatus: () => MOCK ? Promise.resolve(M.dailyStatus()) : req('/api/daily/status'),
  dailyClaim: () => MOCK ? Promise.resolve(M.dailyClaim()) : req('/api/daily/claim', { method: 'POST' }),
  ravensUnread: () => MOCK ? Promise.resolve(M.ravensUnread()) : req('/api/ravens/unread'),
  inbox:     () => MOCK ? Promise.resolve(M.inbox()) : req('/api/ravens/inbox'),
  thread:    (otherTgId) => MOCK ? Promise.resolve(M.thread(otherTgId)) : req('/api/ravens/thread/' + otherTgId),
  sendRaven: (toTgIds, text) => MOCK ? Promise.resolve(M.sendRaven(toTgIds, text))
    : req('/api/ravens/send', { method: 'POST', body: JSON.stringify({ to_tg_ids: toTgIds, text }) }),
  buildings: (castle) => MOCK ? Promise.resolve(M.buildings(castle)) : req('/api/buildings' + (castle ? '?castle=' + encodeURIComponent(castle) : '')),
  buildBuilding:   (id, castle) => MOCK ? Promise.resolve(M.buildAction(id, false, castle)) : req('/api/buildings/build',   { method: 'POST', body: JSON.stringify({ building_id: id, castle }) }),
  upgradeBuilding: (id, castle) => MOCK ? Promise.resolve(M.buildAction(id, true, castle))  : req('/api/buildings/upgrade', { method: 'POST', body: JSON.stringify({ building_id: id, castle }) }),
  sendRumor: (targetTgId, text) => MOCK ? Promise.resolve(M.sendRumor(targetTgId, text))
    : req('/api/rumors/send', { method: 'POST', body: JSON.stringify({ target_tg_id: targetTgId, text }) }),
  listRumors: () => MOCK ? Promise.resolve(M.listRumors()) : req('/api/rumors'),
  markRumorsSeen: () => MOCK ? Promise.resolve(M.markRumorsSeen()) : req('/api/rumors/seen', { method: 'POST' }),
  reactRumor: (rumorId, reaction) => MOCK ? Promise.resolve(M.reactRumor(rumorId, reaction))
    : req(`/api/rumors/${rumorId}/react`, { method: 'POST', body: JSON.stringify({ reaction }) }),
  adminRumors: () => MOCK ? Promise.resolve([]) : req('/api/admin/rumors'),
  adminDeleteRumor: (id) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/admin/rumors/${id}`, { method: 'DELETE' }),
  adminCleanupPreview: () => MOCK ? Promise.resolve({ messages: 0, rumors: 0, campaigns: 0, reports: 0, protected: { active_campaigns: 0, pending_spy: 0, pending_roleplays: 0 } }) : req('/api/admin/cleanup/preview'),
  adminCleanup: (category, confirm) => MOCK ? Promise.resolve({ ok: true, deleted: 0 }) : req('/api/admin/cleanup', { method: 'POST', body: JSON.stringify({ category, confirm }) }),
  adminNotifications: () => MOCK ? Promise.resolve([]) : req('/api/admin/notifications'),
  adminReadNotification: (id) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/admin/notifications/${id}/read`, { method: 'POST' }),
  adminReadAllNotifications: () => MOCK ? Promise.resolve({ ok: true }) : req('/api/admin/notifications/read-all', { method: 'POST' }),
  adminListPendingPlayers: () => MOCK ? Promise.resolve(M.adminListPendingPlayers()) : req('/api/admin/players/pending'),
  adminListRoster: () => MOCK ? Promise.resolve(M.adminListRoster()) : req('/api/admin/players/roster'),
  adminSyncTelegramUsernames: () => MOCK ? Promise.resolve({ ok: true, total: 1, found: 1, no_username: 0, unavailable: 0 })
    : req('/api/admin/players/sync-telegram-usernames', { method: 'POST' }),
  adminUnassignHouse: (tgId) => MOCK ? Promise.resolve(M.adminUnassignHouse(tgId)) : req(`/api/admin/players/${tgId}/unassign`, { method: 'POST' }),
  adminDeletePendingPlayer: (tgId) => MOCK ? Promise.resolve(M.adminDeletePendingPlayer(tgId)) : req(`/api/admin/players/${tgId}/pending`, { method: 'DELETE' }),
  adminAssignHouse: (tgId, region, castle) => MOCK ? Promise.resolve(M.adminAssignHouse(tgId, region, castle))
    : req(`/api/admin/players/${tgId}/assign`, { method: 'POST', body: JSON.stringify({ region, castle }) }),
  adminAddCastle: (tgId, castle) => MOCK ? Promise.resolve(M.adminAddCastle(tgId, castle))
    : req(`/api/admin/players/${tgId}/castles`, { method: 'POST', body: JSON.stringify({ castle }) }),
  adminRemoveCastle: (tgId, castle) => MOCK ? Promise.resolve(M.adminRemoveCastle(tgId, castle))
    : req(`/api/admin/players/${tgId}/castles/${encodeURIComponent(castle)}`, { method: 'DELETE' }),
  myCastles: () => MOCK ? Promise.resolve(M.myCastles()) : req('/api/assets/castles'),
  castleAssets: (castle) => MOCK ? Promise.resolve(M.castleAssets(castle)) : req('/api/assets/castle' + (castle ? '?castle=' + encodeURIComponent(castle) : '')),
  myItems: () => MOCK ? Promise.resolve(M.myItems()) : req('/api/assets/items'),
  adminListItems: () => MOCK ? Promise.resolve(M.adminListItems()) : req('/api/admin/items'),
  adminCreateItem: (b) => MOCK ? Promise.resolve(M.adminCreateItem(b)) : req('/api/admin/items', { method: 'POST', body: JSON.stringify(b) }),
  adminDeleteItem: (id) => MOCK ? Promise.resolve(M.adminDeleteItem(id)) : req(`/api/admin/items/${id}`, { method: 'DELETE' }),
  adminGrantItem: (itemId, tgId, color) => MOCK ? Promise.resolve(M.adminGrantItem(itemId, tgId, color))
    : req(`/api/admin/items/${itemId}/grant`, { method: 'POST', body: JSON.stringify({ tg_id: tgId, color }) }),
  adminGetBuildingBalance: () => MOCK ? Promise.resolve(M.adminGetBuildingBalance()) : req('/api/admin/building-balance'),
  adminSetBuildingBalance: (b) => MOCK ? Promise.resolve(M.adminSetBuildingBalance(b))
    : req('/api/admin/building-balance', { method: 'POST', body: JSON.stringify(b) }),
  adminResetBuildingBalance: (id) => MOCK ? Promise.resolve(M.adminResetBuildingBalance(id))
    : req(`/api/admin/building-balance/${id}/reset`, { method: 'POST' }),
  adminGetGameplayBalance: () => MOCK ? Promise.resolve(M.adminGetGameplayBalance()) : req('/api/admin/gameplay-balance'),
  adminSetGameplayBalance: (b) => MOCK ? Promise.resolve(M.adminSetGameplayBalance(b)) : req('/api/admin/gameplay-balance', { method: 'POST', body: JSON.stringify(b) }),
  adminResetGameplayBalance: () => MOCK ? Promise.resolve(M.adminResetGameplayBalance()) : req('/api/admin/gameplay-balance/reset', { method: 'POST' }),
  adminPlayerBuildings: (tgId) => MOCK ? Promise.resolve({ castles: [], max_level: 30 })
    : req(`/api/admin/players/${tgId}/buildings`),
  adminSetPlayerBuilding: (tgId, buildingId, castle, level) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/admin/players/${tgId}/buildings/${buildingId}`, { method: 'POST', body: JSON.stringify({ castle, level }) }),
  setTax:    (rate) => MOCK ? Promise.resolve(M.setTax(rate)) : req('/api/players/tax', { method: 'POST', body: JSON.stringify({ rate }) }),
  titles:    () => MOCK ? Promise.resolve(M.titles()) : req('/api/titles'),
  setSmallCouncil: (seat, tgId) => MOCK ? Promise.resolve(M.setSmallCouncil(seat, tgId))
    : req('/api/titles/small-council', { method: 'POST', body: JSON.stringify({ seat, tg_id: tgId }) }),
  setCouncilSalary: (seat, amount) => MOCK ? Promise.resolve(M.setCouncilSalary(seat, amount))
    : req('/api/titles/council-salary', { method: 'POST', body: JSON.stringify({ seat, amount }) }),
  setKingSalary: (amount) => MOCK ? Promise.resolve(M.setKingSalary(amount))
    : req('/api/titles/king-salary', { method: 'POST', body: JSON.stringify({ amount }) }),
  tributeMine: () => MOCK ? Promise.resolve(M.tributeMine()) : req('/api/tribute/mine'),
  demandTribute: (toTgId, amount) => MOCK ? Promise.resolve(M.demandTribute(toTgId, amount))
    : req('/api/tribute/demand', { method: 'POST', body: JSON.stringify({ to_tg_id: toTgId, amount }) }),
  payTribute: (id) => MOCK ? Promise.resolve(M.payTribute(id))
    : req(`/api/tribute/${id}/pay`, { method: 'POST' }),
  diplomacyMine: () => MOCK ? Promise.resolve(M.diplomacyMine()) : req('/api/diplomacy/mine'),
  diplomacyPublic: () => MOCK ? Promise.resolve(M.diplomacyPublic()) : req('/api/diplomacy/public'),
  diplomacyPropose: (toTgIds, type, name, isPrivate, penaltyGold) => MOCK ? Promise.resolve(M.diplomacyPropose(toTgIds, type, name, isPrivate, penaltyGold))
    : req('/api/diplomacy/propose', { method: 'POST', body: JSON.stringify({ to_tg_ids: toTgIds, type, name, private: !!isPrivate, penalty_gold: penaltyGold || 0 }) }),
  diplomacyRespond: (id, accept) => MOCK ? Promise.resolve(M.diplomacyRespond(id, accept))
    : req(`/api/diplomacy/${id}/respond`, { method: 'POST', body: JSON.stringify({ accept }) }),
  diplomacyLeave: (id) => MOCK ? Promise.resolve(M.diplomacyLeave(id))
    : req(`/api/diplomacy/${id}/leave`, { method: 'POST' }),
  adminListAlliances: () => MOCK ? Promise.resolve(M.adminListAlliances()) : req('/api/admin/alliances'),
  adminDissolveAlliance: (id) => MOCK ? Promise.resolve(M.adminDissolveAlliance(id))
    : req(`/api/admin/alliances/${id}/dissolve`, { method: 'POST' }),
  feast: () => MOCK ? Promise.resolve(M.feast()) : req('/api/diplomacy/feast', { method: 'POST' }),
  regionLeaderboard: () => MOCK ? Promise.resolve(M.regionLeaderboard()) : req('/api/leaderboard/regions'),
  polls: () => MOCK ? Promise.resolve(M.polls()) : req('/api/polls'),
  vote:  (id, option) => MOCK ? Promise.resolve(M.vote(id, option)) : req(`/api/polls/${id}/vote`, { method: 'POST', body: JSON.stringify({ option }) }),
  searchPlayers: (q) => MOCK ? Promise.resolve(M.searchPlayers(q)) : req('/api/players/search?q=' + encodeURIComponent(q)),

  /* ---------- شورش و محبوبیت ---------- */
  rebellionStatus: () => MOCK ? Promise.resolve((() => {
    const popularity = mockMe.popularity ?? 50;
    const taxRate = mockMe.tax_rate ?? 10;
    const taxHeavyThreshold = Math.max(0, Math.min(100, 20 + Math.floor((popularity - 50) / 5)));
    const taxBands = [{ max: 5, p: 2 }, { max: 10, p: 1 }, { max: 15, p: 0 }, { max: 20, p: -1 }, { max: 100, p: -2 }];
    const baseTax = (taxBands.find(b => taxHeavyThreshold <= b.max) || taxBands.at(-1)).p;
    const taxDelta = taxRate > taxHeavyThreshold ? baseTax - Math.ceil((taxRate - taxHeavyThreshold) / 5)
      : (taxBands.find(b => taxRate <= b.max) || taxBands.at(-1)).p;
    const levels = {
      very_low: { label: 'جیره ناچیز', multiplier: .5, popularity: -3 },
      low: { label: 'جیره کم', multiplier: .75, popularity: -1 },
      normal: { label: 'جیره معمولی', multiplier: 1, popularity: 0 },
      good: { label: 'جیره خوب', multiplier: 1.25, popularity: 1 },
      abundant: { label: 'جیره فراوان', multiplier: 1.5, popularity: 2 },
    };
    const ration = mockMe.food_ration || 'normal';
    const men = mockMe.resources?.men || 0;
    const food = Math.round(Math.max(1, men * .2) * levels[ration].multiplier);
    const rationDelta = (mockMe.resources?.food || 0) >= food ? levels[ration].popularity : -3;
    return {
      popularity, ration, chance: 0, safe_popularity: 50, guaranteed_popularity: 30,
      ration_levels: levels, tax_rate: taxRate, tax_heavy_threshold: taxHeavyThreshold,
      tax_daily_popularity: taxDelta, ration_daily_popularity: rationDelta,
      combined_daily_popularity: taxDelta + rationDelta, ration_food_per_day: food,
      estimated_tax_gold_per_day: Math.round(men * taxRate / 100 * taxYieldMultiplier(popularity)),
      tax_yield_percent: Math.round(taxYieldMultiplier(popularity) * 100), active: null,
    };
  })()) : req('/api/rebellions/status'),
  setFoodRation: (level) => MOCK ? Promise.resolve((mockMe.food_ration = level, { ok: true, ration: level }))
    : req('/api/rebellions/ration', { method: 'POST', body: JSON.stringify({ level }) }),
  submitRebellionRoleplay: (id, text) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/rebellions/${id}/roleplay`, { method: 'POST', body: JSON.stringify({ text }) }),
  adminRebellionSettings: () => MOCK ? Promise.resolve(null) : req('/api/rebellions/admin/settings'),
  adminSaveRebellionSettings: (settings) => MOCK ? Promise.resolve(settings)
    : req('/api/rebellions/admin/settings', { method: 'POST', body: JSON.stringify({ settings }) }),
  adminRebellions: () => MOCK ? Promise.resolve([]) : req('/api/rebellions/admin/list'),
  adminResolveRebellion: (id, body) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/rebellions/admin/${id}/resolve`, { method: 'POST', body: JSON.stringify(body) }),

  /* ---------- پنل ادمین ---------- */
  adminCampaigns: () => MOCK ? Promise.resolve(M.adminCampaigns()) : req('/api/admin/campaigns'),
  adminAmbushes: () => MOCK ? Promise.resolve([]) : req('/api/admin/ambushes'),
  adminScoreAmbush: (id, coefficient, ambushScore) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/admin/ambushes/${id}/score`, { method: 'POST', body: JSON.stringify({ coefficient, ambush_score: ambushScore }) }),
  adminPlayerCampaigns: (tgId) => MOCK ? Promise.resolve(M.adminPlayerCampaigns(tgId)) : req(`/api/admin/players/${tgId}/campaigns`),
  adminDisbandCampaign: (id) => MOCK ? Promise.resolve(M.adminDisbandCampaign(id)) : req(`/api/admin/campaigns/${id}/disband`, { method: 'POST' }),
  adminDestroyCampaign: (id) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/admin/campaigns/${id}/destroy`, { method: 'POST' }),
  adminReduceCampaign: (id, troops) => MOCK ? Promise.resolve({ ok: true }) : req(`/api/admin/campaigns/${id}/reduce`, { method: 'POST', body: JSON.stringify({ troops }) }),

  /* ---------- جاسوسی ---------- */
  sendSpy: (targetCastle, scenario) => MOCK ? Promise.resolve(M.sendSpy(targetCastle, scenario))
    : req('/api/espionage/send', { method: 'POST', body: JSON.stringify({ target_castle: targetCastle, scenario }) }),
  spyMine: () => MOCK ? Promise.resolve(M.spyMine()) : req('/api/espionage/mine'),
  adminSpyPending: () => MOCK ? Promise.resolve(M.adminSpyPending()) : req('/api/admin/espionage'),
  adminSpyResolved: () => MOCK ? Promise.resolve(M.adminSpyResolved()) : req('/api/admin/espionage/resolved'),
  adminScoreSpy: (missionId, score) => MOCK ? Promise.resolve(M.adminScoreSpy(missionId, score))
    : req(`/api/admin/espionage/${missionId}/score`, { method: 'POST', body: JSON.stringify({ score }) }),

  /* ---------- رول‌ها ---------- */
  sendRoleplay: (category, text, campaignId, targetTgId = null) => MOCK ? Promise.resolve(M.sendRoleplay(category, text, campaignId))
    : req('/api/roleplay/send', { method: 'POST', body: JSON.stringify({ category, text, campaign_id: campaignId, target_tg_id: targetTgId }) }),
  roleplayMine: () => MOCK ? Promise.resolve(M.roleplayMine()) : req('/api/roleplay/mine'),
  adminRoleplayPending: () => MOCK ? Promise.resolve(M.adminRoleplayPending()) : req('/api/admin/roleplay'),
  adminSecurityRoleplays: (query = '', tgId = null) => MOCK ? Promise.resolve([])
    : req(`/api/admin/roleplay/security?q=${encodeURIComponent(query)}${tgId ? `&tg_id=${tgId}` : ''}`),
  adminBattles: () => MOCK ? Promise.resolve([]) : req('/api/admin/battles'),
  adminResolveBattle: (campaignId, result, visibility, winnerTgIds, attackerLosses = {}, defenderLosses = {}, attackerEquipmentLosses = {}, defenderEquipmentLosses = {}, attackerArmyLosses = {}, attackerArmyEquipmentLosses = {}, defenderArmyLosses = {}, defenderArmyEquipmentLosses = {}, imageUrl = null) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/admin/battles/${campaignId}/resolve`, { method: 'POST', body: JSON.stringify({ result, visibility: visibility || 'participants', winner_tg_ids: winnerTgIds, winner_tg_id: winnerTgIds?.[0] || null, attacker_losses: attackerLosses, defender_losses: defenderLosses, attacker_equipment_losses: attackerEquipmentLosses, defender_equipment_losses: defenderEquipmentLosses, attacker_army_losses: attackerArmyLosses, attacker_army_equipment_losses: attackerArmyEquipmentLosses, defender_army_losses: defenderArmyLosses, defender_army_equipment_losses: defenderArmyEquipmentLosses, image_url: imageUrl }) }),
  adminDismissBattle: (campaignId) => MOCK ? Promise.resolve({ ok: true })
    : req(`/api/admin/battles/${campaignId}/dismiss`, { method: 'POST' }),
  adminRespondRoleplay: (roleplayId, result, visibility, otherLords = [], winnerTgId = null, attackerLosses = {}, defenderLosses = {}, adjustments = {}) => MOCK ? Promise.resolve(M.adminRespondRoleplay(roleplayId, result, visibility, otherLords, winnerTgId))
    : req(`/api/admin/roleplay/${roleplayId}/respond`, { method: 'POST', body: JSON.stringify({ result, visibility: visibility || 'participants', other_lords: otherLords, winner_tg_id: winnerTgId, attacker_losses: attackerLosses, defender_losses: defenderLosses, actor_resource_deltas: adjustments.actorResources || {}, actor_popularity_delta: Number(adjustments.actorPopularity || 0), target_resource_deltas: adjustments.targetResources || {}, target_popularity_delta: Number(adjustments.targetPopularity || 0) }) }),
  warRoleplayEligible: () => MOCK ? Promise.resolve(M.warRoleplayEligible()) : req('/api/war/roleplay-eligible'),

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
  adminDeletePoll: (id) => MOCK ? Promise.resolve(M.adminDeletePoll()) : req(`/api/polls/admin/${id}`, { method: 'DELETE' }),
  adminListAdmins: () => MOCK ? Promise.resolve(M.adminListAdmins()) : req('/api/admin/admins'),
  adminAddAdmin: (tgId, role = 'limited') => MOCK ? Promise.resolve(M.adminAddAdmin())
    : req('/api/admin/admins', { method: 'POST', body: JSON.stringify({ tg_id: tgId, role }) }),
  adminRemoveAdmin: (tgId) => MOCK ? Promise.resolve(M.adminRemoveAdmin())
    : req(`/api/admin/admins/${tgId}`, { method: 'DELETE' }),
  adminResetGamePreview: () => MOCK ? Promise.resolve(M.adminResetGamePreview()) : req('/api/admin/reset-game/preview'),
  adminResetGame: (confirm) => MOCK ? Promise.resolve(M.adminResetGame(confirm))
    : req('/api/admin/reset-game', { method: 'POST', body: JSON.stringify({ confirm }) }),
  adminResetSeason: (confirm) => MOCK ? Promise.resolve({ ok: true, players_reset: mockPlayers.length })
    : req('/api/admin/reset-season', { method: 'POST', body: JSON.stringify({ confirm }) }),
  adminResetScoreboard: (confirm) => MOCK ? Promise.resolve({ ok: true, players_reset: mockPlayers.length })
    : req('/api/admin/reset-scoreboard', { method: 'POST', body: JSON.stringify({ confirm }) }),
};
