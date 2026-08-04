export const REGIONS_STATIC = {
  north: { name: 'شمال', g: 'شم', special: ["نگهبان شمال", "سوار زمستان"],
    castles: ['اولد کستل','باروتاون','تورنز اسکوئر','دردفورت','رمزگیت','شدو تاور','لست هارت','موت کلین','وینترفل','کسل بلک','گری واتر واچ'],
    ports: ['اسکاگوس','ایست واچ','بیر آیلند','دیپ وود موت','فلینتز فینگر','وایت هاربر','ویدوز واچ','کارهولد'] },
  iron: { name: 'جزایر آهن', g: 'جز', special: ["غارتگر آهن", "جنگجوی تبردار"],
    castles: [],
    ports: ['اورکمونت','اولد ویک','بلک تاید','تن تاورز','سالت کلیف','پایک','گریت ویک'] },
  river: { name: 'ریورلندز', g: 'ری', special: ["پیادهٔ رودخانه", "کماندار باتلاق"],
    castles: ['استونی سپت','اولد استونز','اکرون هال','این آف د نیلینگ من','تویینز','ریوران','ریونتری هال','سالت پنس','فیر مارکت','لرد هارویز تاون','هارنهال','هورن ویل','ویکندن','پینک میدن'],
    ports: ['سیگارد','میدنپول'] },
  west: { name: 'وسترلندز', g: 'وس', special: ["پیادهٔ زره‌سنگین", "شوالیه لنیستری"],
    castles: ['اشمارک','دیپ دن','ردلیک','سارس فیلد','سیلورهیل','فیست فایرز','کرگ','کریک هال','کلگانزکیپ','کورن فیلد','گولدن توث'],
    ports: ['بینفورت','فیرکسل','لنیسپورت'] },
  reach: { name: 'ریچ', g: 'رچ', special: ["کماندار ریچ", "سوار زره‌دار ریچ"],
    castles: ['آپلندز','اشفورد','برایت واتر کیپ','بلک کرون','بیتتر بریج','تامبلتون','تری تاورز','سامرهال','سیدر هال','لانگ تیبل','هاروست هال','هانی هولت','هایگاردن','گرسسی ویل','گولدن گرو'],
    ports: ['آربور','اولد اوک','اولد تاون','باندالون'] },
  vale: { name: 'درهٔ آرین', g: 'در', special: ["نیزه‌دار کوهستان", "سوار دره"],
    castles: ['آیرون اوکس','استرانگ سانگ','اسنیک وود','اولد انکر','ایری','بلادی گیت','ردفورت','لانگ بو هال','هارتز هوم','کولد واتر'],
    ports: ['بیلیش کیپ','ران استون','لیتل سیستر','گالتاون'] },
  storm: { name: 'استورملندز', g: 'اس', special: ["جنگجوی طوفان", "سوار طوفان"],
    castles: ['استون دنس','برونزگیت','بلک هیون','رین هوس','فلوود','میست وود','نایت سانگ','های استک هال','کروز نست','گریفینز روست'],
    ports: ['استورمز اند','استون هلم','ایون فال هال','گرین استون','ویپینگ تاون'] },
  dorne: { name: 'دورن', g: 'دو', special: ["نیزه‌دار دورنی", "سوار شن"],
    castles: ['اسکای ریچ','بلکمونت','تاور آف جوی','تور','سند باکس','لمون وود','های هرمیتیج','هل هولت','ولچرزروست','ویث','ویل','کینگزگریو','گادز گریس'],
    ports: ['استارفال','سالت شور','سان اسپیر','گاستون گری','گوست هیل','یرون وود'] },
  crown: { name: 'کراون‌لندز', g: 'کر', special: [],
    castles: ['آنتلرز','داسکندیل','دایر دن','روزبی'],
    ports: ['دراگون استون','دریفت مارک','روکز رست','شارپ پوینت','کینگزلندینگ'] },
};

// رنگِ اختصاصیِ هر اقلیم — پینِ هر قلعه روی نقشه با همین رنگ نشون داده می‌شه، بر اساس
// region فعلیِ لردِ صاحبش (نه لزوماً جغرافیای خودِ قلعه) — یعنی اگه یه لرد قلعه‌ای
// خارج از اقلیمِ اصلیش رو بگیره، پینِ اون قلعه هم رنگِ اقلیمِ فعلیِ همون لرد می‌شه
export const REGION_COLORS = {
  north: '#7fa8c9',
  iron: '#3fa796',
  river: '#5b7fd4',
  west: '#c9a83a',
  reach: '#6fae52',
  vale: '#b9a6e0',
  storm: '#f2c94c',
  dorne: '#e2703a',
  crown: '#c0392b',
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

// دو نوع کشتی — فقط قلعه/شهرهای خشکی‌دریایی یا کاملاً دریایی می‌توانند بسازندشان؛
// «بندر» به‌جای پادگان+کارگاه تسلیحات پیش‌نیازشان است و سطح بندر مثل سطح پادگان توانشان
// را بالا می‌برد. «capacity» یعنی هر کشتی چند سرباز را می‌تواند حمل کند — برای قلعه‌های
// کاملاً دریایی (بدون راه خشکی) الزامی است (نگاه کن به mapCoords/War.jsx)
export const NAVAL_TROOPS = [
  { id: 'ship',       name: 'کشتی جنگی',       cost: 5, power: 10, capacity: 250 },
  { id: 'cargo_ship', name: 'کشتی سادهٔ چوبی', cost: 3, power: 0,  capacity: 100 },
];
export const NAVAL_TROOP_IDS = NAVAL_TROOPS.map(t => t.id);
export const NAVAL_CAMP_BUILDING = 'port';

// نوع دسترسیِ زمینی/دریاییِ هر قلعه — از پنل ادمین (تب نقشه) روی هر پین مشخص می‌شود
export const MAP_TERRAINS = [
  { key: 'land',    label: 'صرفاً خشکی' },
  { key: 'coastal', label: 'خشکی‌دریایی' },
  { key: 'sea',     label: 'کاملاً دریایی' },
];
export const FOOD_COST_REGULAR = 1;   // غله در روز، به‌ازای هر سرباز عادی
export const FOOD_COST_SPECIAL = 2;   // غله در روز، به‌ازای هر نیروی ویژه

// پیش‌نیاز اعزام هر نیروی عمومی: فقط پادگانِ همان یگان باید ساخته شده باشد — کارگاه
// تسلیحات دیگر پیش‌نیاز نیست، فقط منبع تسلیحاتی‌ست که موقع اعزام مصرف می‌شود (weapon کلید زیر)
export const TROOP_UNIT_BUILDINGS = {
  heavy_cav: { camp: 'camp_hcav',   armory: 'armory_hcav',   weapon: 'weapon_hcav' },
  infantry:  { camp: 'camp_sword',  armory: 'armory_sword',  weapon: 'weapon_sword' },
  light_cav: { camp: 'camp_lcav',   armory: 'armory_lcav',   weapon: 'weapon_lcav' },
  archer:    { camp: 'camp_archer', armory: 'armory_archer', weapon: 'weapon_archer' },
  spearman:  { camp: 'camp_spear',  armory: 'armory_spear',  weapon: 'weapon_spear' },
};
export const WEAPON_PER_SOLDIER = 1;
export const WEAPON_NAMES = {
  weapon_sword:  'سلاح پیاده‌نظام',
  weapon_spear:  'سلاح نیزه‌داران',
  weapon_archer: 'سلاح کمانداران',
  weapon_lcav:   'سلاح سوارهٔ سبک',
  weapon_hcav:   'سلاح سوارهٔ سنگین',
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
    } else if (NAVAL_TROOP_IDS.includes(tid)) {
      const naval = NAVAL_TROOPS.find(t => t.id === tid);
      const portLevel = builtLevels?.[NAVAL_CAMP_BUILDING] || 0;
      total += naval.power * (1 + portLevel * CAMP_POWER_STEP) * n;
    } else {
      total += SPECIAL_POWER * n;
    }
  }
  return Math.round(total);
}

// خاندانِ حاکمِ هر قلعه — آینه‌ی CASTLE_HOUSES در backend/game_data.py
// (هر تغییری اونجا دادی، اینجا هم بده تا هم‌راستا بمونن)
export const CASTLE_HOUSES = {
  'آربور': 'ردواین',
  'آنتلرز': null,
  'آپلندز': null,
  'آیرون اوکس': 'لیندرلی',
  'استارفال': 'داین',
  'استرانگ سانگ': 'بلمور',
  'استورمز اند': 'باراتیون',
  'استون دنس': null,
  'استون هلم': 'سوان',
  'استونی سپت': null,
  'اسنیک وود': 'ولز',
  'اسکاگوس': 'استین',
  'اسکای ریچ': 'فاولر',
  'اشفورد': 'اشفورد',
  'اشمارک': 'ماربرند',
  'اورکمونت': 'گودبرادر',
  'اولد استونز': null,
  'اولد انکر': null,
  'اولد اوک': 'اوک‌هارت',
  'اولد تاون': 'های‌تاور',
  'اولد ویک': 'گودبرادر',
  'اولد کستل': 'لاک',
  'اکرون هال': 'اسمال‌وود',
  'ایری': 'آرین',
  'ایست واچ': null,
  'این آف د نیلینگ من': null,
  'ایون فال هال': 'تارت',
  'باروتاون': 'داستین',
  'باندالون': null,
  'برایت واتر کیپ': 'فلورنت',
  'برونزگیت': 'باکلر',
  'بلادی گیت': null,
  'بلک تاید': 'بلک‌تاید',
  'بلک هیون': 'دندریون',
  'بلک کرون': null,
  'بلکمونت': 'بلک‌مونت',
  'بیتتر بریج': 'کاسول',
  'بیر آیلند': 'مورمانت',
  'بیلیش کیپ': 'بیلیش',
  'بینفورت': 'بینفورت',
  'تامبلتون': 'فوتلی',
  'تاور آف جوی': null,
  'تری تاورز': 'کاستین',
  'تن تاورز': 'هارلو',
  'تور': 'کورگایل',
  'تورنز اسکوئر': 'تال‌هارت',
  'تویینز': 'فری',
  'داسکندیل': 'ریکر',
  'دایر دن': null,
  'دراگون استون': 'تارگرین',
  'دردفورت': 'بولتون',
  'دریفت مارک': 'ولاریون',
  'دیپ دن': 'تاربک',
  'دیپ وود موت': 'گلاور',
  'ران استون': 'رویس',
  'ردفورت': 'ردفورت',
  'ردلیک': 'کرین',
  'رمزگیت': null,
  'روزبی': 'روزبی',
  'روکز رست': 'استانتون',
  'رین هوس': 'واگستاف',
  'ریوران': 'تالی',
  'ریونتری هال': 'بلک‌وود',
  'سارس فیلد': 'سارس‌فیلد',
  'سالت شور': null,
  'سالت پنس': 'کاکس',
  'سالت کلیف': 'سالت‌کلیف',
  'سامرهال': null,
  'سان اسپیر': 'مارتل',
  'سند باکس': null,
  'سیدر هال': null,
  'سیلورهیل': 'سرت',
  'سیگارد': 'مالیستر',
  'شارپ پوینت': 'بار امون',
  'شدو تاور': null,
  'فلوود': null,
  'فلینتز فینگر': 'فلینت',
  'فیر مارکت': null,
  'فیرکسل': 'فارمن',
  'فیست فایرز': null,
  'لانگ بو هال': 'هانتر',
  'لانگ تیبل': 'مری‌ودر',
  'لرد هارویز تاون': null,
  'لست هارت': 'آمبر',
  'لمون وود': 'دالت',
  'لنیسپورت': 'لنیستر',
  'لیتل سیستر': 'ساندرلند',
  'موت کلین': null,
  'میدنپول': 'موتون',
  'میست وود': 'مرتینز',
  'نایت سانگ': 'کارون',
  'هارتز هوم': 'کوربری',
  'هارنهال': 'ونت',
  'هاروست هال': 'بیزبری',
  'هانی هولت': null,
  'های استک هال': null,
  'های هرمیتیج': null,
  'هایگاردن': 'تایرل',
  'هل هولت': 'اولر',
  'هورن ویل': null,
  'وایت هاربر': 'ماندرلی',
  'ولچرزروست': null,
  'ویث': 'ویث',
  'ویدوز واچ': 'فلینت',
  'ویل': 'ویل',
  'وینترفل': 'استارک',
  'ویپینگ تاون': null,
  'ویکندن': 'وود',
  'پایک': 'گریجوی',
  'پینک میدن': 'پایپر',
  'کارهولد': 'کارستارک',
  'کروز نست': 'موریگن',
  'کرگ': 'وسترلینگ',
  'کریک هال': 'کریک‌هال',
  'کسل بلک': null,
  'کلگانزکیپ': 'کلگان',
  'کورن فیلد': 'پرستر',
  'کولد واتر': 'کولدواتر',
  'کینگزلندینگ': null,
  'کینگزگریو': 'من‌وودی',
  'گادز گریس': 'آلیریون',
  'گاستون گری': null,
  'گالتاون': 'گرافتون',
  'گرسسی ویل': null,
  'گری واتر واچ': 'رید',
  'گریت ویک': null,
  'گریفینز روست': 'کانینگتون',
  'گرین استون': 'استرمونت',
  'گوست هیل': 'تولند',
  'گولدن توث': 'لفورد',
  'گولدن گرو': 'رووان',
  'یرون وود': 'یرون‌وود',
};

// نامِ انگلیسیِ هر قلعه — آینه‌ی CASTLE_EN_NAMES در backend/game_data.py
export const CASTLE_EN_NAMES = {
  'آربور': 'The Arbor',
  'آنتلرز': 'Antlers',
  'آپلندز': 'Uplands',
  'آیرون اوکس': 'Ironoaks',
  'استارفال': 'Starfall',
  'استرانگ سانگ': 'Strongsong',
  'استورمز اند': 'Storm\'s End',
  'استون دنس': 'Stonedance',
  'استون هلم': 'Stonehelm',
  'استونی سپت': 'Stoney Sept',
  'اسنیک وود': 'Snakewood',
  'اسکاگوس': 'Skagos',
  'اسکای ریچ': 'Skyreach',
  'اشفورد': 'Ashford',
  'اشمارک': 'Ashemark',
  'اورکمونت': 'Orkmont',
  'اولد استونز': 'Oldstones',
  'اولد انکر': 'Old Anchor',
  'اولد اوک': 'Old Oak',
  'اولد تاون': 'Oldtown',
  'اولد ویک': 'Old Wyk',
  'اولد کستل': 'Old Castle',
  'اکرون هال': 'Acorn Hall',
  'ایری': 'Eyrie',
  'ایست واچ': 'Eastwatch-by-the-Sea',
  'این آف د نیلینگ من': 'Inn of the Kneeling Man',
  'ایون فال هال': 'Evenfall Hall',
  'باروتاون': 'Barrowton',
  'باندالون': 'Bandallon',
  'برایت واتر کیپ': 'Brightwater Keep',
  'برونزگیت': 'Bronzegate',
  'بلادی گیت': 'Bloody Gate',
  'بلک تاید': 'Blacktyde',
  'بلک هیون': 'Blackhaven',
  'بلک کرون': 'Black Crown',
  'بلکمونت': 'Blackmont',
  'بیتتر بریج': 'Bitterbridge',
  'بیر آیلند': 'Bear Island',
  'بیلیش کیپ': 'Baelish Keep',
  'بینفورت': 'Banefort',
  'تامبلتون': 'Tumbleton',
  'تاور آف جوی': 'Tower of Joy',
  'تری تاورز': 'Three Towers',
  'تن تاورز': 'Ten Towers',
  'تور': 'The Tor',
  'تورنز اسکوئر': 'Torrhen\'s Square',
  'تویینز': 'The Twins',
  'داسکندیل': 'Duskendale',
  'دایر دن': 'Dyre Den',
  'دراگون استون': 'Dragonstone',
  'دردفورت': 'Dreadfort',
  'دریفت مارک': 'Driftmark',
  'دیپ دن': 'Deep Den',
  'دیپ وود موت': 'Deepwood Motte',
  'ران استون': 'Runestone',
  'ردفورت': 'Redfort',
  'ردلیک': 'Red Lake',
  'رمزگیت': 'Ramsgate',
  'روزبی': 'Rosby',
  'روکز رست': 'Rook\'s Rest',
  'رین هوس': 'Rain House',
  'ریوران': 'Riverrun',
  'ریونتری هال': 'Raventree Hall',
  'سارس فیلد': 'Sarsfield',
  'سالت شور': 'Salt Shore',
  'سالت پنس': 'Saltpans',
  'سالت کلیف': 'Saltcliffe',
  'سامرهال': 'Summerhall',
  'سان اسپیر': 'Sunspear',
  'سند باکس': 'Sandstone',
  'سیدر هال': 'Cedar Hall',
  'سیلورهیل': 'Silverhill',
  'سیگارد': 'Seagard',
  'شارپ پوینت': 'Sharp Point',
  'شدو تاور': 'Shadow Tower',
  'فلوود': 'Felwood',
  'فلینتز فینگر': 'Flint\'s Finger',
  'فیر مارکت': 'Fairmarket',
  'فیرکسل': 'Faircastle',
  'فیست فایرز': 'Feastfires',
  'لانگ بو هال': 'Longbow Hall',
  'لانگ تیبل': 'Longtable',
  'لرد هارویز تاون': 'Lord Harroway\'s Town',
  'لست هارت': 'Last Hearth',
  'لمون وود': 'Lemonwood',
  'لنیسپورت': 'Lannisport',
  'لیتل سیستر': 'Little Sister',
  'موت کلین': 'Moat Cailin',
  'میدنپول': 'Maidenpool',
  'میست وود': 'Mistwood',
  'نایت سانگ': 'Nightsong',
  'هارتز هوم': 'Heart\'s Home',
  'هارنهال': 'Harrenhal',
  'هاروست هال': 'Harvest Hall',
  'هانی هولت': 'Honeyholt',
  'های استک هال': 'Haystack Hall',
  'های هرمیتیج': 'High Hermitage',
  'هایگاردن': 'Highgarden',
  'هل هولت': 'Hellholt',
  'هورن ویل': 'Hornvale',
  'وایت هاربر': 'White Harbor',
  'ولچرزروست': 'Vulture\'s Roost',
  'ویث': 'Vaith',
  'ویدوز واچ': 'Widow\'s Watch',
  'ویل': 'Wyl',
  'وینترفل': 'Winterfell',
  'ویپینگ تاون': 'Weeping Town',
  'ویکندن': 'Wickenden',
  'پایک': 'Pyke',
  'پینک میدن': 'Pinkmaiden',
  'کارهولد': 'Karhold',
  'کروز نست': 'Crow\'s Nest',
  'کرگ': 'Crag',
  'کریک هال': 'Crakehall',
  'کسل بلک': 'Castle Black',
  'کلگانزکیپ': 'Clegane\'s Keep',
  'کورن فیلد': 'Cornfield',
  'کولد واتر': 'Coldwater Burn',
  'کینگزلندینگ': 'King\'s Landing',
  'کینگزگریو': 'Kingsgrave',
  'گادز گریس': 'Godsgrace',
  'گاستون گری': 'Ghaston Grey',
  'گالتاون': 'Gulltown',
  'گرسسی ویل': 'Grassy Vale',
  'گری واتر واچ': 'Greywater Watch',
  'گریت ویک': 'Great Wyk',
  'گریفینز روست': 'Griffin\'s Roost',
  'گرین استون': 'Greenstone',
  'گوست هیل': 'Ghost Hill',
  'گولدن توث': 'Golden Tooth',
  'گولدن گرو': 'Goldengrove',
  'یرون وود': 'Yronwood',
};

// برای نمایش: «فارسی (English)» — اگه اسمِ انگلیسی نداشتیم (قلعهٔ دست‌سازِ ادمین)
// همون فارسی تنها برمی‌گرده
export function castleLabel(name) {
  const en = CASTLE_EN_NAMES[name];
  return en ? `${name} (${en})` : (name || '');
}

// زمان سفر لشکر — گراف واقعیِ قلعه‌به‌قلعه، خوانده‌شده از روی خودِ نقشهٔ بازی
// (همون گراف backend/game_data.py — هر تغییری اونجا دادی، اینجا هم بده تا هم‌راستا بمونن)
const CASTLE_TRAVEL_EDGES = [
  ['کسل بلک', 'ایست واچ', 30],
  ['کسل بلک', 'شدو تاور', 30],
  ['کسل بلک', 'لست هارت', 30],
  ['ایست واچ', 'اسکاگوس', 10],
  ['اسکاگوس', 'ویدوز واچ', 60],
  ['لست هارت', 'کارهولد', 60],
  ['لست هارت', 'دردفورت', 30],
  ['لست هارت', 'وینترفل', 60],
  ['کارهولد', 'ویدوز واچ', 30],
  ['دردفورت', 'ویدوز واچ', 30],
  ['دردفورت', 'وایت هاربر', 60],
  ['وینترفل', 'دیپ وود موت', 30],
  ['وینترفل', 'موت کلین', 60],
  ['وینترفل', 'تورنز اسکوئر', 30],
  ['دیپ وود موت', 'بیر آیلند', 10],
  ['بیر آیلند', 'فلینتز فینگر', 70],
  ['بیر آیلند', 'گریت ویک', 90],
  ['تورنز اسکوئر', 'باروتاون', 30],
  ['باروتاون', 'موت کلین', 30],
  ['موت کلین', 'وایت هاربر', 10],
  ['موت کلین', 'فلینتز فینگر', 60],
  ['موت کلین', 'گری واتر واچ', 30],
  ['وایت هاربر', 'رمزگیت', 30],
  ['وایت هاربر', 'اولد کستل', 10],
  ['وایت هاربر', 'لیتل سیستر', 10],
  ['لیتل سیستر', 'ویدوز واچ', 40],
  ['لیتل سیستر', 'گالتاون', 90],
  ['فلینتز فینگر', 'گریت ویک', 40],
  ['گری واتر واچ', 'تویینز', 30],
  ['ویدوز واچ', 'گالتاون', 70],
  ['تویینز', 'سیگارد', 5],
  ['تویینز', 'اولد استونز', 10],
  ['تویینز', 'لرد هارویز تاون', 60],
  ['سیگارد', 'تن تاورز', 30],
  ['اولد استونز', 'ریونتری هال', 5],
  ['اولد استونز', 'فیر مارکت', 10],
  ['ریونتری هال', 'ریوران', 5],
  ['ریوران', 'گولدن توث', 30],
  ['ریوران', 'این آف د نیلینگ من', 30],
  ['ریوران', 'اکرون هال', 10],
  ['ریوران', 'هورن ویل', 60],
  ['این آف د نیلینگ من', 'لرد هارویز تاون', 30],
  ['لرد هارویز تاون', 'سالت پنس', 5],
  ['لرد هارویز تاون', 'هارنهال', 10],
  ['لرد هارویز تاون', 'بلادی گیت', 60],
  ['سالت پنس', 'ویکندن', 60],
  ['اکرون هال', 'پینک میدن', 10],
  ['اکرون هال', 'استونی سپت', 10],
  ['اکرون هال', 'هارنهال', 30],
  ['هارنهال', 'میدنپول', 30],
  ['هارنهال', 'کینگزلندینگ', 60],
  ['میدنپول', 'آنتلرز', 10],
  ['میدنپول', 'روکز رست', 30],
  ['میدنپول', 'گالتاون', 30],
  ['روکز رست', 'دایر دن', 60],
  ['روکز رست', 'دراگون استون', 10],
  ['روکز رست', 'داسکندیل', 30],
  ['آنتلرز', 'داسکندیل', 10],
  ['داسکندیل', 'روزبی', 10],
  ['روزبی', 'کینگزلندینگ', 10],
  ['بلادی گیت', 'ایری', 5],
  ['ایری', 'ردفورت', 30],
  ['ایری', 'آیرون اوکس', 10],
  ['ایری', 'استرانگ سانگ', 30],
  ['استرانگ سانگ', 'هارتز هوم', 10],
  ['هارتز هوم', 'اسنیک وود', 10],
  ['اسنیک وود', 'کولد واتر', 30],
  ['آیرون اوکس', 'اولد انکر', 10],
  ['اولد انکر', 'بیلیش کیپ', 30],
  ['بیلیش کیپ', 'لانگ بو هال', 10],
  ['ران استون', 'بیلیش کیپ', 10],
  ['ردفورت', 'گالتاون', 30],
  ['گالتاون', 'ران استون', 5],
  ['گالتاون', 'دراگون استون', 30],
  ['دراگون استون', 'دریفت مارک', 5],
  ['دراگون استون', 'ایون فال هال', 30],
  ['دریفت مارک', 'شارپ پوینت', 5],
  ['دریفت مارک', 'کینگزلندینگ', 30],
  ['شارپ پوینت', 'استون دنس', 5],
  ['گریت ویک', 'اولد ویک', 5],
  ['گریت ویک', 'پایک', 5],
  ['اولد ویک', 'اورکمونت', 5],
  ['اورکمونت', 'بلک تاید', 5],
  ['اورکمونت', 'تن تاورز', 5],
  ['پایک', 'سالت کلیف', 5],
  ['پایک', 'بینفورت', 5],
  ['پایک', 'تن تاورز', 5],
  ['پایک', 'فیرکسل', 10],
  ['بینفورت', 'کرگ', 30],
  ['کرگ', 'اشمارک', 30],
  ['اشمارک', 'سارس فیلد', 30],
  ['سارس فیلد', 'گولدن توث', 10],
  ['سارس فیلد', 'لنیسپورت', 10],
  ['لنیسپورت', 'فیست فایرز', 30],
  ['لنیسپورت', 'دیپ دن', 30],
  ['لنیسپورت', 'کلگانزکیپ', 5],
  ['لنیسپورت', 'کریک هال', 60],
  ['لنیسپورت', 'اولد اوک', 50],
  ['لنیسپورت', 'باندالون', 60],
  ['لنیسپورت', 'آربور', 90],
  ['لنیسپورت', 'فیرکسل', 20],
  ['دیپ دن', 'کینگزلندینگ', 120],
  ['سیلورهیل', 'دیپ دن', 60],
  ['سیلورهیل', 'گولدن گرو', 30],
  ['کلگانزکیپ', 'کورن فیلد', 5],
  ['کورن فیلد', 'ردلیک', 10],
  ['ردلیک', 'اولد اوک', 30],
  ['کریک هال', 'اولد اوک', 60],
  ['اولد اوک', 'فیرکسل', 50],
  ['اولد اوک', 'هایگاردن', 60],
  ['گولدن گرو', 'هایگاردن', 30],
  ['هایگاردن', 'سیدر هال', 10],
  ['هایگاردن', 'کینگزلندینگ', 120],
  ['هایگاردن', 'نایت سانگ', 30],
  ['هایگاردن', 'هورن ویل', 10],
  ['هایگاردن', 'اولد تاون', 60],
  ['سیدر هال', 'اشفورد', 10],
  ['سیدر هال', 'لانگ تیبل', 10],
  ['لانگ تیبل', 'گرسسی ویل', 30],
  ['گرسسی ویل', 'بیتتر بریج', 10],
  ['بیتتر بریج', 'تامبلتون', 30],
  ['اشفورد', 'هاروست هال', 30],
  ['هاروست هال', 'سامرهال', 10],
  ['استون دنس', 'های استک هال', 60],
  ['های استک هال', 'برونزگیت', 5],
  ['برونزگیت', 'استورمز اند', 10],
  ['برونزگیت', 'فلوود', 10],
  ['فلوود', 'سامرهال', 30],
  ['سامرهال', 'بلک هیون', 30],
  ['سامرهال', 'ویل', 60],
  ['بلک هیون', 'نایت سانگ', 30],
  ['ویل', 'ولچرزروست', 30],
  ['ویل', 'یرون وود', 60],
  ['نایت سانگ', 'تاور آف جوی', 10],
  ['تاور آف جوی', 'کینگزگریو', 30],
  ['کینگزگریو', 'بلکمونت', 30],
  ['کینگزگریو', 'اسکای ریچ', 10],
  ['اسکای ریچ', 'یرون وود', 30],
  ['یرون وود', 'گاستون گری', 5],
  ['یرون وود', 'تور', 30],
  ['گاستون گری', 'استون هلم', 10],
  ['گاستون گری', 'ویپینگ تاون', 30],
  ['ویپینگ تاون', 'گرین استون', 10],
  ['ویپینگ تاون', 'گوست هیل', 10],
  ['ویپینگ تاون', 'میست وود', 10],
  ['گرین استون', 'ایون فال هال', 10],
  ['گرین استون', 'سان اسپیر', 30],
  ['میست وود', 'استون هلم', 30],
  ['میست وود', 'رین هوس', 30],
  ['استون هلم', 'کروز نست', 30],
  ['کروز نست', 'گریفینز روست', 30],
  ['گریفینز روست', 'استورمز اند', 30],
  ['استورمز اند', 'ایون فال هال', 10],
  ['سان اسپیر', 'گوست هیل', 10],
  ['سان اسپیر', 'گادز گریس', 30],
  ['سان اسپیر', 'سالت شور', 40],
  ['سان اسپیر', 'استارفال', 100],
  ['سان اسپیر', 'آربور', 100],
  ['گادز گریس', 'لمون وود', 10],
  ['گادز گریس', 'سالت شور', 10],
  ['گادز گریس', 'ویث', 30],
  ['گادز گریس', 'تور', 10],
  ['سالت شور', 'استارفال', 80],
  ['سالت شور', 'آربور', 80],
  ['ویث', 'هل هولت', 30],
  ['هل هولت', 'سند باکس', 30],
  ['سند باکس', 'استارفال', 60],
  ['استارفال', 'آربور', 20],
  ['استارفال', 'های هرمیتیج', 5],
  ['های هرمیتیج', 'بلکمونت', 5],
  ['آربور', 'اولد تاون', 10],
  ['اولد تاون', 'تری تاورز', 5],
  ['اولد تاون', 'آپلندز', 5],
  ['اولد تاون', 'بلک کرون', 5],
  ['اولد تاون', 'هانی هولت', 5],
  ['هانی هولت', 'برایت واتر کیپ', 5],
  ['برایت واتر کیپ', 'باندالون', 10],
  ['باندالون', 'آربور', 40],
  ['باندالون', 'اولد اوک', 30],
];

function buildTravelGraph() {
  const graph = {};
  for (const [a, b, mins] of CASTLE_TRAVEL_EDGES) {
    graph[a] = graph[a] || {};
    graph[b] = graph[b] || {};
    graph[a][b] = Math.min(graph[a][b] ?? mins, mins);
    graph[b][a] = Math.min(graph[b][a] ?? mins, mins);
  }
  return graph;
}
const TRAVEL_GRAPH = buildTravelGraph();
const TRAVEL_CROSS_REGION_DEFAULT_MINUTES = 90;

// یال‌های دریایی — آینه‌ی SEA_EDGES در backend/game_data.py (نگه‌داری‌شان یکسان لازم است)
export const SEA_EDGES = new Set([
  ['ایست واچ', 'اسکاگوس'], ['اسکاگوس', 'ویدوز واچ'],
  ['دیپ وود موت', 'بیر آیلند'], ['بیر آیلند', 'فلینتز فینگر'], ['بیر آیلند', 'گریت ویک'],
  ['وایت هاربر', 'لیتل سیستر'], ['لیتل سیستر', 'ویدوز واچ'], ['لیتل سیستر', 'گالتاون'],
  ['فلینتز فینگر', 'گریت ویک'], ['سیگارد', 'تن تاورز'],
  ['گریت ویک', 'اولد ویک'], ['گریت ویک', 'پایک'], ['اولد ویک', 'اورکمونت'],
  ['اورکمونت', 'بلک تاید'], ['اورکمونت', 'تن تاورز'], ['پایک', 'سالت کلیف'],
  ['پایک', 'بینفورت'], ['پایک', 'تن تاورز'], ['پایک', 'فیرکسل'],
  ['لنیسپورت', 'فیرکسل'], ['اولد اوک', 'فیرکسل'],
  ['لنیسپورت', 'آربور'], ['سان اسپیر', 'آربور'], ['سالت شور', 'آربور'],
  ['استارفال', 'آربور'], ['آربور', 'اولد تاون'], ['باندالون', 'آربور'],
  ['یرون وود', 'گاستون گری'], ['گاستون گری', 'استون هلم'], ['گاستون گری', 'ویپینگ تاون'],
  ['دراگون استون', 'ایون فال هال'], ['استورمز اند', 'ایون فال هال'], ['گرین استون', 'ایون فال هال'],
  ['روکز رست', 'دراگون استون'], ['گالتاون', 'دراگون استون'],
  ['دراگون استون', 'دریفت مارک'], ['دریفت مارک', 'شارپ پوینت'], ['دریفت مارک', 'کینگزلندینگ'],
  ['ویپینگ تاون', 'گرین استون'], ['گرین استون', 'سان اسپیر'],
].map(([a, b]) => [a, b].sort().join('|')));

// قلعه‌هایی که پیش‌فرضشان کاملاً دریایی‌ست — آینه‌ی DEFAULT_SEA_CASTLES در backend
export const DEFAULT_SEA_CASTLES = new Set(['گرین استون']);

export function isSeaEdge(a, b, terrain) {
  if (SEA_EDGES.has([a, b].sort().join('|'))) return true;
  if (terrain && (terrain(a) === 'sea' || terrain(b) === 'sea')) return true;
  return false;
}
export function pathUsesSea(path, terrain) {
  for (let i = 0; i < path.length - 1; i++) if (isSeaEdge(path[i], path[i + 1], terrain)) return true;
  return false;
}

function shortestMinutes(originCastle, targetCastle) {
  if (!TRAVEL_GRAPH[originCastle] || !TRAVEL_GRAPH[targetCastle]) return TRAVEL_CROSS_REGION_DEFAULT_MINUTES;
  const dist = { [originCastle]: 0 };
  const seen = new Set();
  const pq = [[0, originCastle]];
  while (pq.length) {
    pq.sort((a, b) => a[0] - b[0]);
    const [d, node] = pq.shift();
    if (seen.has(node)) continue;
    seen.add(node);
    if (node === targetCastle) return d;
    for (const [nb, w] of Object.entries(TRAVEL_GRAPH[node] || {})) {
      const nd = d + w;
      if (nd < (dist[nb] ?? Infinity)) {
        dist[nb] = nd;
        pq.push([nd, nb]);
      }
    }
  }
  return TRAVEL_CROSS_REGION_DEFAULT_MINUTES;
}

export function travelMinutes(sameCastle, originCastle, targetCastle) {
  if (sameCastle) return 0;
  return shortestMinutes(originCastle, targetCastle);
}

function dijkstraPath(originCastle, targetCastle, allowSea = true, terrain) {
  // قلعه‌ای که ادمین تازه به نقشه اضافه کرده و هنوز به گراف سفرِ ثابت وصل نشده —
  // مثلِ shortestMinutes یه مسیرِ مستقیمِ پیش‌فرض می‌دیم، وگرنه لشکرکشی/کاروان بهش
  // کاملاً و برای همیشه غیرممکن می‌موند
  if (!TRAVEL_GRAPH[originCastle] || !TRAVEL_GRAPH[targetCastle]) {
    return { minutes: TRAVEL_CROSS_REGION_DEFAULT_MINUTES, path: [originCastle, targetCastle] };
  }
  const dist = { [originCastle]: 0 };
  const prev = {};
  const seen = new Set();
  const pq = [[0, originCastle]];
  while (pq.length) {
    pq.sort((a, b) => a[0] - b[0]);
    const [d, node] = pq.shift();
    if (seen.has(node)) continue;
    seen.add(node);
    if (node === targetCastle) {
      const path = [node];
      while (path[path.length - 1] !== originCastle) path.push(prev[path[path.length - 1]]);
      path.reverse();
      return { minutes: d, path };
    }
    for (const [nb, w] of Object.entries(TRAVEL_GRAPH[node] || {})) {
      if (!allowSea && isSeaEdge(node, nb, terrain)) continue;
      const nd = d + w;
      if (nd < (dist[nb] ?? Infinity)) {
        dist[nb] = nd;
        prev[nb] = node;
        pq.push([nd, nb]);
      }
    }
  }
  return { minutes: null, path: null };
}

// یک یا دو گزینهٔ مسیرِ واقعی بین دو قلعهٔ متفاوت — آینه‌ی travel_routes در
// backend/game_data.py؛ اگه یالِ روی بهترین مسیر رو موقتاً حذف کنیم و دوباره
// دایکسترا بزنیم، ممکنه یه مسیرِ واقعاً متفاوت (نه فقط دورتر روی همون یال‌ها) پیدا بشه
export function travelRoutes(originCastle, targetCastle, maxRoutes = 2, allowSea = true, terrain) {
  const best = dijkstraPath(originCastle, targetCastle, allowSea, terrain);
  if (!best.path) return [];
  const routes = [{ minutes: best.minutes, path: best.path, via_sea: pathUsesSea(best.path, terrain) }];
  if (maxRoutes <= 1 || best.path.length < 2) return routes;

  const seenPaths = new Set([best.path.join('→')]);
  const candidates = [];
  for (let i = 0; i < best.path.length - 1; i++) {
    const a = best.path[i], b = best.path[i + 1];
    const wAB = TRAVEL_GRAPH[a]?.[b];
    const wBA = TRAVEL_GRAPH[b]?.[a];
    if (wAB !== undefined) delete TRAVEL_GRAPH[a][b];
    if (wBA !== undefined) delete TRAVEL_GRAPH[b][a];
    const alt = dijkstraPath(originCastle, targetCastle, allowSea, terrain);
    if (wAB !== undefined) TRAVEL_GRAPH[a][b] = wAB;
    if (wBA !== undefined) TRAVEL_GRAPH[b][a] = wBA;
    if (alt.path && !seenPaths.has(alt.path.join('→'))) {
      seenPaths.add(alt.path.join('→'));
      candidates.push({ minutes: alt.minutes, path: alt.path, via_sea: pathUsesSea(alt.path, terrain) });
    }
  }
  if (candidates.length) {
    candidates.sort((x, y) => x.minutes - y.minutes);
    routes.push(candidates[0]);
  }
  return routes.slice(0, maxRoutes);
}

// جاسوس‌ها سریع‌تر از لشکر حرکت می‌کنند
export const SPY_GOLD_COST = 1000;
export const SPY_MEN_COST = 5;
const SPY_SPEED_FACTOR = 0.4;

export function spyTravelMinutes(originCastle, targetCastle) {
  if (originCastle === targetCastle) return 0;
  return Math.max(1, Math.round(shortestMinutes(originCastle, targetCastle) * SPY_SPEED_FACTOR));
}

// گزینه‌های عملیات لشکرکشی
export const OP_TYPES = [
  { id: 'attack',     name: 'حملهٔ نظامی',                          needsTarget: true,  portOnly: false, landOnly: false },
  { id: 'siege',      name: 'محاصرهٔ قلعه (فقط اهداف غیربندری)',    needsTarget: true,  portOnly: false, landOnly: true },
  { id: 'naval_raid', name: 'غارت دریایی (برای اهداف بندری)',       needsTarget: true,  portOnly: true,  landOnly: false },
  { id: 'garrison',   name: 'جای‌گیری',                              needsTarget: true,  portOnly: false, landOnly: false },
  { id: 'defense',    name: 'دفاعی',                                needsTarget: false, portOnly: false, landOnly: false },
];

// نبردهای واقعی — بعد از رسیدن، هر دو طرف تا ROLEPLAY_WINDOW_HOURS ساعت فرصت دارند
// سناریوی جنگ را از صفحهٔ رول‌ها (دستهٔ جنگ) بفرستند
export const ATTACK_OP_TYPES = ['attack', 'siege', 'naval_raid'];
export const DEFENSE_OP_TYPES = ['defense', 'garrison'];
export const ROLEPLAY_WINDOW_HOURS = 6;
// ۲۴ ساعت بعد از رسیدن، گزارش لشکرکشی از تب گزارش‌های بازیکن پاک می‌شود
export const REPORT_VISIBLE_HOURS = 24;

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
  warehouse:   { name: 'انبار',        cost: { gold: 220, stone: 70, wood: 60 }, hours: 5,  type: 'economy', cap_bonus: { food: 40, stone: 15, iron: 15 } },
  treasury:    { name: 'خزانه',        cost: { gold: 350, stone: 100, wood: 80 }, hours: 6,  type: 'economy', cap_bonus: { gold: 300 } },
  // پادگان هر یگان
  camp_sword:  { name: 'پادگان پیاده‌نظام',   cost: { gold: 250, iron: 50,  wood: 90 },  hours: 6,  type: 'barracks', unit: 'infantry' },
  camp_spear:  { name: 'پادگان نیزه‌داران',   cost: { gold: 200, iron: 30,  wood: 70 },  hours: 5,  type: 'barracks', unit: 'spearman' },
  camp_archer: { name: 'پادگان کمانداران',    cost: { gold: 200, iron: 20,  wood: 80 },  hours: 5,  type: 'barracks', unit: 'archer' },
  camp_lcav:   { name: 'پادگان سوارهٔ سبک',   cost: { gold: 350, iron: 60,  wood: 110 }, hours: 8,  type: 'barracks', unit: 'light_cav' },
  camp_hcav:   { name: 'پادگان سوارهٔ سنگین', cost: { gold: 500, iron: 120, wood: 140 }, hours: 12, type: 'barracks', unit: 'heavy_cav' },
  // کارگاه تسلیحات هر یگان — ساختمان تولیدی است، تسلیحاتِ همان یگان را روزانه طبق سطحش می‌سازد
  armory_sword:  { name: 'کارگاه تسلیحات پیاده‌نظام',   cost: { gold: 200, iron: 80,  wood: 40 }, hours: 6,  type: 'armory', unit: 'infantry',  produces: { weapon_sword: 6 } },
  armory_spear:  { name: 'کارگاه تسلیحات نیزه‌داران',   cost: { gold: 160, iron: 60,  wood: 40 }, hours: 5,  type: 'armory', unit: 'spearman',  produces: { weapon_spear: 6 } },
  armory_archer: { name: 'کارگاه تسلیحات کمانداران',    cost: { gold: 160, iron: 50,  wood: 60 }, hours: 5,  type: 'armory', unit: 'archer',    produces: { weapon_archer: 6 } },
  armory_lcav:   { name: 'کارگاه تسلیحات سوارهٔ سبک',   cost: { gold: 280, iron: 100, wood: 50 }, hours: 8,  type: 'armory', unit: 'light_cav', produces: { weapon_lcav: 4 } },
  armory_hcav:   { name: 'کارگاه تسلیحات سوارهٔ سنگین', cost: { gold: 400, iron: 180, wood: 60 }, hours: 12, type: 'armory', unit: 'heavy_cav', produces: { weapon_hcav: 3 } },
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

// بازدهی/سقفِ سراسری‌ای که ادمین از تب «تعادل بازی» بازنویسی کرده — آینه‌ی
// BUILDING_OVERRIDES در backend/game_data.py، فقط برای حالت MOCK (چون اینجا
// دیتابیسی نیست که این بازنویسی‌ها رو نگه داره، در همین حافظهٔ مرورگر می‌مونن)
export const BUILDING_OVERRIDES = {};

export function buildingProduces(id) {
  const override = BUILDING_OVERRIDES[id];
  if (override && override.produces) return override.produces;
  return BUILDINGS_STATIC[id].produces || {};
}

export function buildingCapBonus(id) {
  const override = BUILDING_OVERRIDES[id];
  if (override && override.cap_bonus) return override.cap_bonus;
  return BUILDINGS_STATIC[id].cap_bonus || {};
}

// بازدهیِ فعلیِ یک ساختمان — تولید روزانه و افزایش سقفِ ذخیره‌سازی، به‌نسبت سطح فعلی‌اش
export function buildingYield(id, level) {
  const produces = Object.fromEntries(Object.entries(buildingProduces(id)).map(([k, v]) => [k, v * level]));
  const capBonus = Object.fromEntries(Object.entries(buildingCapBonus(id)).map(([k, v]) => [k, v * level]));
  return { produces, cap_bonus: capBonus };
}

export const WARDEN_GROUPS = {
  south:   { name: 'والی جنوب', regions: ['reach', 'dorne', 'storm'] },
  central: { name: 'والی مرکز', regions: ['west', 'crown', 'river'] },
  north:   { name: 'والی شمال', regions: ['north', 'iron', 'vale'] },
};

// رول‌ها — بازیکن سناریوی آزاد می‌نویسد، دسته‌بندی می‌کند، ادمین نتیجه را می‌نویسد
// «جاسوسی» عمداً اینجا نیست — همان کار را با مکانیزم اختصاصی‌اش (امتیاز→شانس) در بخش جاسوسی انجام می‌دهد
export const ROLEPLAY_CATEGORIES = {
  war:       'جنگ',
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
// رنگِ پین روی نقشه در حالتِ «رنگ‌بندی بر اساسِ پیمان»
export const PACT_COLORS = {
  full_alliance:  '#57b872',
  non_aggression: '#4da3ff',
  trade:          '#b06cf0',
  none:           '#8a93a3',
};
// پیمان خصوصی (توی تب عمومیِ «اتحادها» نشان داده نمی‌شود) دو برابر شرابِ معمولی هزینه دارد
export const PRIVATE_ALLIANCE_MULTIPLIER = 2;
// اولویتِ نمایش وقتی با یک نفر چند پیمان هم‌زمان برقرار است — قوی‌ترین رابطه رنگ پین را روی نقشه تعیین می‌کند
export const PACT_PRIORITY = ['full_alliance', 'non_aggression', 'trade'];

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

// جایزهٔ ورود روزانه — چرخهٔ ۷ روزه با منحنی افزایشی (باید با DAILY_REWARDS بک‌اند یکی بماند)
export const DAILY_REWARDS = [
  { gold: 50 },
  { gold: 80,  food: 40 },
  { gold: 120, food: 60 },
  { gold: 180, wood: 40, stone: 40 },
  { gold: 260, iron: 40, men: 20 },
  { gold: 350, wine: 10, men: 30 },
  { gold: 600, men: 80,  wine: 20, food: 200 },
];

export function maxTaxRate(popularity) {
  return Math.max(0, TAX_RATE_BASE_MAX + Math.floor((popularity - POPULARITY_START) / 5));
}

// تولید/سقفِ پایه (بدون ساختمان) — آینه‌ی DAILY_PRODUCTION/RESOURCE_CAPS در backend/config.py
export const DAILY_PRODUCTION = { gold: 200, food: 300, men: 50, iron: 40, stone: 40, wood: 50, wine: 0 };
export const RESOURCE_CAPS = {
  gold: 2000, food: 2000, men: 1000, iron: 500, stone: 500, wood: 800, wine: 300,
  weapon_sword: 300, weapon_spear: 300, weapon_archer: 300, weapon_lcav: 200, weapon_hcav: 200,
};
export function taxYieldMultiplier(popularity) {
  return 0.5 + popularity / (2 * POPULARITY_MAX);
}

// کالاهایی که می‌شود کاروان فرستاد یا از بازار وستروس خرید — طلا خودش پول است، نه کالا
export const TRADE_GOODS = ['wood', 'stone', 'iron', 'food', 'wine'];
export const TRADE_GOOD_NAMES = { wood: 'چوب', stone: 'سنگ', iron: 'آهن', food: 'غذا', wine: 'شراب' };
