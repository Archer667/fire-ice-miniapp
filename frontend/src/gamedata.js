export const REGIONS_STATIC = {
  north: { name: 'شمال', g: 'شم', special: ['نگهبان شمال', 'سوار زمستان'],
    castles: ['وینترفل','دردفورت','بارولندز','کارهولد','لاست‌هرت','تورنز اسکوئر','دیپ‌وود موت','موات کیلین','قلعهٔ سروین','تال‌هارت','فلینت'],
    ports: ['وایت هاربر','بارو‌تاون','بندر دیپ‌وود'] },
  iron: { name: 'جزایر آهن', g: 'جز', special: ['غارتگر آهن', 'جنگجوی تبردار'],
    castles: ['پایک','هارلاو هال','تن تاور','بلک‌تاید','اورکمونت','سالت‌کلیف'],
    ports: ['لردپورت','بندر هارلاو'] },
  river: { name: 'ریورلندز', g: 'ری', special: ['پیادهٔ رودخانه', 'کماندار باتلاق'],
    castles: ['ریورران','هارنهال','دوقلوها','سیگارد','راونتری','استون‌هج','آکورن هال','دارری'],
    ports: ['میدن‌پول','سالت‌پنس'] },
  west: { name: 'وسترلندز', g: 'وس', special: ['پیادهٔ زره‌سنگین', 'شوالیه لنیستری'],
    castles: ['کسترلی راک','کریگ','کی‌هال','گلدن‌توث','فرکسل'],
    ports: ['لنیسپورت'] },
  reach: { name: 'ریچ', g: 'رچ', special: ['کماندار ریچ', 'سوار زره‌دار ریچ'],
    castles: ['های‌گاردن','هورن‌هیل','تارلی‌هال','بریج‌واتر','آشبروک','ردلیک','سان‌هوس'],
    ports: ['اولدتاون','بیتربریج'] },
  vale: { name: 'درهٔ آرین', g: 'در', special: ['نیزه‌دار کوهستان', 'سوار دره'],
    castles: ['ایری','گیتس آو د مون','ران‌استون','هارتز هوم','ردفورت','لانگ‌بو هال'],
    ports: ['گال‌تاون'] },
  storm: { name: 'استورملندز', g: 'اس', special: ['جنگجوی طوفان', 'سوار طوفان'],
    castles: ['استورمز اند','گریفینز روست','تارث','رین‌هال','فل‌وود'],
    ports: ['شیپ‌بریک بی'] },
  dorne: { name: 'دورن', g: 'دو', special: ['نیزه‌دار دورنی', 'سوار شن'],
    castles: ['سان‌اسپیر','واتر گاردنز','استارفال','یرونوود','اسکای‌ریچ','هل‌هولت'],
    ports: ['پلنکی‌تاون','بندر استارفال'] },
  crown: { name: 'کراون‌لندز', g: 'کر', special: [],
    castles: ['رد کیپ','دراگون‌استون','روزبی','استوک‌ورث','دارک‌لین هال'],
    ports: ['کینگز لندینگ'] },
};

export const COMMON_TROOPS = [
  { id: 'heavy_cav', name: 'سواره‌نظام سنگین', cost: 3, power: 6 },
  { id: 'infantry',  name: 'پیاده‌نظام',       cost: 2, power: 4 },
  { id: 'light_cav', name: 'سواره‌نظام سبک',   cost: 2, power: 4 },
  { id: 'archer',    name: 'کماندار',           cost: 1, power: 3 },
  { id: 'spearman',  name: 'نیزه‌دار',          cost: 1, power: 2 },
];
export const SPECIAL_COST = 4;
export const SPECIAL_POWER = 5;       // نیروهای ویژه پادگان ندارند، پس توانشان ثابت است
export const CAMP_POWER_STEP = 0.05;  // هر سطح پادگانِ یک یگان، توان همان یگان را ۵٪ بالا می‌برد

// کشتی جنگی — فقط قلعه/شهرهای بندری می‌توانند بسازندش؛ «بندر» به‌جای پادگان+کارگاه
// تسلیحات پیش‌نیازش است و سطح بندر مثل سطح پادگان توان کشتی را بالا می‌برد
export const NAVAL_TROOP = { id: 'ship', name: 'کشتی جنگی', cost: 5, power: 10 };
export const NAVAL_CAMP_BUILDING = 'port';
export const FOOD_COST_REGULAR = 1;   // غله در روز، به‌ازای هر سرباز عادی
export const FOOD_COST_SPECIAL = 2;   // غله در روز، به‌ازای هر نیروی ویژه

// پیش‌نیاز اعزام هر نیروی عمومی: پادگان + کارگاه تسلیحاتِ همان یگان باید ساخته شده باشد
export const TROOP_UNIT_BUILDINGS = {
  heavy_cav: { camp: 'camp_hcav',   armory: 'armory_hcav' },
  infantry:  { camp: 'camp_sword',  armory: 'armory_sword' },
  light_cav: { camp: 'camp_lcav',   armory: 'armory_lcav' },
  archer:    { camp: 'camp_archer', armory: 'armory_archer' },
  spearman:  { camp: 'camp_spear',  armory: 'armory_spear' },
};

// توان کل یک لشکر — troops: {troop_id: count}, builtLevels: {building_id: level}
export function campaignPower(troops, builtLevels) {
  let total = 0;
  for (const [tid, n] of Object.entries(troops || {})) {
    if (!n || n <= 0) continue;
    const common = COMMON_TROOPS.find(t => t.id === tid);
    if (common) {
      const req = TROOP_UNIT_BUILDINGS[tid];
      const campLevel = (req && builtLevels?.[req.camp]) || 0;
      total += common.power * (1 + campLevel * CAMP_POWER_STEP) * n;
    } else if (tid === NAVAL_TROOP.id) {
      const portLevel = builtLevels?.[NAVAL_CAMP_BUILDING] || 0;
      total += NAVAL_TROOP.power * (1 + portLevel * CAMP_POWER_STEP) * n;
    } else {
      total += SPECIAL_POWER * n;
    }
  }
  return Math.round(total);
}

// زمان سفر لشکر — بر مبنای فاصلهٔ اقلیمی، تقریبی روی محور شمال-جنوب نقشه (هم‌راستا با بک‌اند)
export const REGION_ORDER = { north: 0, vale: 1, iron: 1, river: 1, west: 2, crown: 2, reach: 3, storm: 3, dorne: 4 };
export const TRAVEL_SAME_REGION_MINUTES = 20;
export const TRAVEL_CROSS_BASE_MINUTES = 40;
export const TRAVEL_PER_HOP_MINUTES = 25;

export function travelMinutes(sameCastle, originRegion, targetRegion) {
  if (sameCastle) return 0;
  if (originRegion === targetRegion) return TRAVEL_SAME_REGION_MINUTES;
  const hop = Math.abs((REGION_ORDER[originRegion] ?? 2) - (REGION_ORDER[targetRegion] ?? 2));
  return TRAVEL_CROSS_BASE_MINUTES + hop * TRAVEL_PER_HOP_MINUTES;
}

// جاسوس‌ها سریع‌تر از لشکر حرکت می‌کنند
export const SPY_GOLD_COST = 1000;
export const SPY_MEN_COST = 5;
export const SPY_SAME_REGION_MINUTES = 8;
export const SPY_CROSS_BASE_MINUTES = 15;
export const SPY_PER_HOP_MINUTES = 8;

export function spyTravelMinutes(originRegion, targetRegion) {
  if (originRegion === targetRegion) return SPY_SAME_REGION_MINUTES;
  const hop = Math.abs((REGION_ORDER[originRegion] ?? 2) - (REGION_ORDER[targetRegion] ?? 2));
  return SPY_CROSS_BASE_MINUTES + hop * SPY_PER_HOP_MINUTES;
}

// گزینه‌های عملیات لشکرکشی
export const OP_TYPES = [
  { id: 'attack',     name: 'حملهٔ نظامی',                    needsTarget: true,  portOnly: false },
  { id: 'siege',      name: 'محاصرهٔ قلعه',                    needsTarget: true,  portOnly: false },
  { id: 'naval_raid', name: 'غارت دریایی (برای اهداف بندری)', needsTarget: true,  portOnly: true },
  { id: 'garrison',   name: 'جای‌گیری',                        needsTarget: true,  portOnly: false },
  { id: 'defense',    name: 'دفاعی',                          needsTarget: false, portOnly: false },
];

// نبردهای واقعی — بعد از رسیدن، هر دو طرف تا ROLEPLAY_WINDOW_HOURS ساعت فرصت دارند
// سناریوی جنگ را از صفحهٔ رول‌ها (دستهٔ جنگ) بفرستند
export const ATTACK_OP_TYPES = ['attack', 'siege', 'naval_raid'];
export const DEFENSE_OP_TYPES = ['defense', 'garrison'];
export const ROLEPLAY_WINDOW_HOURS = 6;
// ۲۴ ساعت بعد از رسیدن، گزارش لشکرکشی از تب گزارش‌های بازیکن پاک می‌شود
export const REPORT_VISIBLE_HOURS = 24;
// گزارش لشکرکشی تازه، ۳۰ دقیقه بعد از ارسال در تب «گزارش‌ها» ظاهر می‌شود — نه بی‌درنگ
export const REPORT_DELAY_MINUTES = 30;

export const BUILDINGS_STATIC = {
  // اقتصادی
  lumber_mill: { name: 'چوب‌بری',     cost: { gold: 130, stone: 30 },   hours: 4,  type: 'economy', produces: { wood: 9 } },
  stone_mine:  { name: 'معدن سنگ',   cost: { gold: 150, wood: 60 },    hours: 4,  type: 'economy', produces: { stone: 8 } },
  iron_mine:   { name: 'معدن آهن',   cost: { gold: 200, wood: 80 },    hours: 6,  type: 'economy', produces: { iron: 6 } },
  gold_mine:   { name: 'معدن طلا',   cost: { gold: 400, stone: 100, wood: 100 }, hours: 12, type: 'economy', produces: { gold: 12 } },
  market:      { name: 'بازار',       cost: { gold: 250, wood: 70 },    hours: 6,  type: 'economy', produces: { gold: 3 } },
  village:     { name: 'دهکده',       cost: { gold: 300, stone: 150, iron: 40 }, hours: 8,  type: 'economy', cap_bonus: { men: 40 } },
  farm:        { name: 'مزرعه',       cost: { gold: 100, wood: 50 },    hours: 3,  type: 'economy', produces: { food: 10 } },
  ranch:       { name: 'دامداری',     cost: { gold: 150, wood: 60 },    hours: 4,  type: 'economy', produces: { food: 6 } },
  winery:      { name: 'می‌کده',      cost: { gold: 220, food: 60, wood: 70 }, hours: 6,  type: 'economy', produces: { wine: 5 } },
  granary:     { name: 'انبار غله',   cost: { gold: 200, stone: 50, wood: 60 }, hours: 5,  type: 'economy', cap_bonus: { food: 40 } },
  warehouse:   { name: 'انبار',        cost: { gold: 200, stone: 80, wood: 50 }, hours: 5,  type: 'economy', cap_bonus: { stone: 15, iron: 15 } },
  // پادگان هر یگان
  camp_sword:  { name: 'پادگان پیاده‌نظام',   cost: { gold: 250, iron: 50,  wood: 90 },  hours: 6,  type: 'barracks', unit: 'infantry' },
  camp_spear:  { name: 'پادگان نیزه‌داران',   cost: { gold: 200, iron: 30,  wood: 70 },  hours: 5,  type: 'barracks', unit: 'spearman' },
  camp_archer: { name: 'پادگان کمانداران',    cost: { gold: 200, iron: 20,  wood: 80 },  hours: 5,  type: 'barracks', unit: 'archer' },
  camp_lcav:   { name: 'پادگان سوارهٔ سبک',   cost: { gold: 350, iron: 60,  wood: 110 }, hours: 8,  type: 'barracks', unit: 'light_cav' },
  camp_hcav:   { name: 'پادگان سوارهٔ سنگین', cost: { gold: 500, iron: 120, wood: 140 }, hours: 12, type: 'barracks', unit: 'heavy_cav' },
  // کارگاه تسلیحات هر یگان
  armory_sword:  { name: 'کارگاه تسلیحات پیاده‌نظام',   cost: { gold: 200, iron: 80,  wood: 40 }, hours: 6,  type: 'armory', unit: 'infantry' },
  armory_spear:  { name: 'کارگاه تسلیحات نیزه‌داران',   cost: { gold: 160, iron: 60,  wood: 40 }, hours: 5,  type: 'armory', unit: 'spearman' },
  armory_archer: { name: 'کارگاه تسلیحات کمانداران',    cost: { gold: 160, iron: 50,  wood: 60 }, hours: 5,  type: 'armory', unit: 'archer' },
  armory_lcav:   { name: 'کارگاه تسلیحات سوارهٔ سبک',   cost: { gold: 280, iron: 100, wood: 50 }, hours: 8,  type: 'armory', unit: 'light_cav' },
  armory_hcav:   { name: 'کارگاه تسلیحات سوارهٔ سنگین', cost: { gold: 400, iron: 180, wood: 60 }, hours: 12, type: 'armory', unit: 'heavy_cav' },
  // دفاعی
  port:        { name: 'بندر',         cost: { gold: 600, stone: 200, wood: 260 }, hours: 12, type: 'defense', requires_port: true },
  wall:        { name: 'دیوار دفاعی', cost: { gold: 400, stone: 300, iron: 60 }, hours: 12, type: 'defense' },
  watchtower:  { name: 'برج نگهبانی', cost: { gold: 250, stone: 120, wood: 70 }, hours: 7,  type: 'defense' },
};

export const MAX_BUILDING_LEVEL = 30;
const LEVEL_COST_STEP = 0.15;
// قبلاً ۰٫۱۲ بود — یعنی جمع ساعتِ ۳۰ سطح برای ساختمان‌های سنگین (پایه ≥۱۲ساعت) از
// ۷۲۰ ساعتِ یک دورهٔ ۳۰روزه رد می‌شد و رساندنشان به سطح ۳۰ ریاضاً غیرممکن بود
const LEVEL_HOURS_STEP = 0.06;

export function buildingCost(id, level) {
  const base = BUILDINGS_STATIC[id].cost;
  const mult = 1 + (level - 1) * LEVEL_COST_STEP;
  return Object.fromEntries(Object.entries(base).filter(([, v]) => v).map(([k, v]) => [k, Math.max(1, Math.round(v * mult))]));
}

export function buildingHours(id, level) {
  const base = BUILDINGS_STATIC[id].hours;
  const mult = 1 + (level - 1) * LEVEL_HOURS_STEP;
  return Math.round(base * mult * 10) / 10;
}

// بازدهیِ فعلیِ یک ساختمان — تولید روزانه و افزایش سقفِ ذخیره‌سازی، به‌نسبت سطح فعلی‌اش
export function buildingYield(id, level) {
  const meta = BUILDINGS_STATIC[id];
  const produces = Object.fromEntries(Object.entries(meta.produces || {}).map(([k, v]) => [k, v * level]));
  const capBonus = Object.fromEntries(Object.entries(meta.cap_bonus || {}).map(([k, v]) => [k, v * level]));
  return { produces, cap_bonus: capBonus };
}

export const WARDEN_GROUPS = {
  south:   { name: 'والی جنوب', regions: ['reach', 'dorne', 'storm'] },
  central: { name: 'والی مرکز', regions: ['west', 'crown', 'river'] },
  north:   { name: 'والی شمال', regions: ['north', 'iron', 'vale'] },
};

// رول‌ها — بازیکن سناریوی آزاد می‌نویسد، دسته‌بندی می‌کند، ادمین نتیجه را می‌نویسد
export const ROLEPLAY_CATEGORIES = {
  war:       'جنگ',
  espionage: 'جاسوسی',
  diplomacy: 'دیپلماسی',
  economy:   'اقتصاد',
  other:     'آزاد',
};

// آیتم‌ها — دارایی‌های شخصی هر لرد؛ ادمین قالبشان را می‌سازد و به لردها می‌دهد
export const ITEM_TYPES = { war: 'جنگی', economy: 'اقتصادی', stealth: 'مخفی‌کاری' };
export const ITEM_DURATIONS = { temporary: 'موقتی', permanent: 'دائمی' };
// «رنگ» میزان خاص‌بودن آیتم را نشان می‌دهد — ادمین موقع دادن آیتم به هر لرد جداگانه انتخابش می‌کند
export const ITEM_RARITY_COLORS = { gray: 'خاکستری', blue: 'آبی', purple: 'بنفش', gold: 'طلایی' };
export const ITEM_RARITY_HEX = { gray: '#9aa5b1', blue: '#4da3ff', purple: '#b06cf0', gold: '#e0b84a' };

// شورای کوچک پادشاه — فقط خودِ پادشاه/ملکهٔ فعلی می‌تواند این کرسی‌ها را بچیند
export const SMALL_COUNCIL_SEATS = {
  hand:     'دست پادشاه',
  coin:     'استاد سکه',
  whispers: 'استاد نجواها',
  ships:    'استاد کشتی‌ها',
  laws:     'استاد قوانین',
  war:      'استاد جنگ',
};

export const ALLIANCE_TYPES = {
  non_aggression: { name: 'پیمان عدم‌تجاوز', wine_cost: 20 },
  trade:          { name: 'پیمان تجاری',      wine_cost: 30 },
  full_alliance:  { name: 'اتحاد کامل',       wine_cost: 60 },
};
// پیمان خصوصی (توی تب عمومیِ «اتحادها» نشان داده نمی‌شود) دو برابر شرابِ معمولی هزینه دارد
export const PRIVATE_ALLIANCE_MULTIPLIER = 2;

export const DEFAULT_TITLE = { lord: 'لرد جوان', lady: 'لیدی جوان' };
export const POPULARITY_START = 50;
export const POPULARITY_MAX = 100;
export const TAX_RATE_DEFAULT = 10;
export const TAX_RATE_BASE_MAX = 20;
export const FEAST_COST = { wine: 40, food: 80 };
export const FEAST_POPULARITY_GAIN = 8;

// شایعات — کارزار عمومی علیه یک بازیکن؛ همه می‌بینند، محبوبیت هدف کم می‌شود
export const RUMOR_GOLD_COST = 100;
export const RUMOR_POPULARITY_DAMAGE = 3;
export const RUMOR_COOLDOWN_HOURS = 6;

export function maxTaxRate(popularity) {
  return Math.max(0, TAX_RATE_BASE_MAX + Math.floor((popularity - POPULARITY_START) / 5));
}

// کالاهایی که می‌شود کاروان فرستاد یا از بازار وستروس خرید — طلا خودش پول است، نه کالا
export const TRADE_GOODS = ['wood', 'stone', 'iron', 'food', 'wine'];
export const TRADE_GOOD_NAMES = { wood: 'چوب', stone: 'سنگ', iron: 'آهن', food: 'غذا', wine: 'شراب' };
