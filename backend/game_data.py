# دیتای ثابت بازی — از فایل «اطلاعات بازی»

REGIONS = {
    "north":  {"name": "شمال", "special": ["نگهبان شمال", "سوار زمستان"],
               "castles": ["وینترفل","دردفورت","بارولندز","کارهولد","لاست‌هرت","تورنز اسکوئر","دیپ‌وود موت","موات کیلین","قلعهٔ سروین","تال‌هارت","فلینت"],
               "ports": ["وایت هاربر","بارو‌تاون","بندر دیپ‌وود"]},
    "iron":   {"name": "جزایر آهن", "special": ["غارتگر آهن", "جنگجوی تبردار"],
               "castles": ["پایک","هارلاو هال","تن تاور","بلک‌تاید","اورکمونت","سالت‌کلیف"],
               "ports": ["لردپورت","بندر هارلاو"]},
    "river":  {"name": "ریورلندز", "special": ["پیادهٔ رودخانه", "کماندار باتلاق"],
               "castles": ["ریورران","هارنهال","دوقلوها","سیگارد","راونتری","استون‌هج","آکورن هال","دارری"],
               "ports": ["میدن‌پول","سالت‌پنس"]},
    "west":   {"name": "وسترلندز", "special": ["پیادهٔ زره‌سنگین", "شوالیه لنیستری"],
               "castles": ["کسترلی راک","کریگ","کی‌هال","گلدن‌توث","فرکسل"],
               "ports": ["لنیسپورت"]},
    "reach":  {"name": "ریچ", "special": ["کماندار ریچ", "سوار زره‌دار ریچ"],
               "castles": ["های‌گاردن","هورن‌هیل","تارلی‌هال","بریج‌واتر","آشبروک","ردلیک","سان‌هوس"],
               "ports": ["اولدتاون","بیتربریج"]},
    "vale":   {"name": "درهٔ آرین", "special": ["نیزه‌دار کوهستان", "سوار دره"],
               "castles": ["ایری","گیتس آو د مون","ران‌استون","هارتز هوم","ردفورت","لانگ‌بو هال"],
               "ports": ["گال‌تاون"]},
    "storm":  {"name": "استورملندز", "special": ["جنگجوی طوفان", "سوار طوفان"],
               "castles": ["استورمز اند","گریفینز روست","تارث","رین‌هال","فل‌وود"],
               "ports": ["شیپ‌بریک بی"]},
    "dorne":  {"name": "دورن", "special": ["نیزه‌دار دورنی", "سوار شن"],
               "castles": ["سان‌اسپیر","واتر گاردنز","استارفال","یرونوود","اسکای‌ریچ","هل‌هولت"],
               "ports": ["پلنکی‌تاون","بندر استارفال"]},
    "crown":  {"name": "کراون‌لندز", "special": [],
               "castles": ["رد کیپ","دراگون‌استون","روزبی","استوک‌ورث","دارک‌لین هال"],
               "ports": ["کینگز لندینگ"]},
}

# ---- والی‌نشین‌ها: هر سه اقلیم زیر یک والی ----
WARDEN_GROUPS = {
    "south":   {"name": "والی جنوب",  "regions": ["reach", "dorne", "storm"]},
    "central": {"name": "والی مرکز",  "regions": ["west", "crown", "river"]},
    "north":   {"name": "والی شمال",  "regions": ["north", "iron", "vale"]},
}

# ---- شورای کوچک پادشاه — فقط خودِ پادشاه/ملکهٔ فعلی می‌تواند این کرسی‌ها را بچیند ----
SMALL_COUNCIL_SEATS = {
    "hand":     "دست پادشاه",
    "coin":     "استاد سکه",
    "whispers": "استاد نجواها",
    "ships":    "استاد کشتی‌ها",
    "laws":     "استاد قوانین",
    "war":      "استاد جنگ",
}

COMMON_TROOPS = {
    "infantry":  {"name": "پیاده‌نظام",       "cost": 2},
    "spearman":  {"name": "نیزه‌دار",          "cost": 1},
    "archer":    {"name": "کماندار",           "cost": 1},
    "light_cav": {"name": "سواره‌نظام سبک",   "cost": 2},
    "heavy_cav": {"name": "سواره‌نظام سنگین", "cost": 3},
}
SPECIAL_TROOP_COST = 4

BUILDINGS = {
    # --- اقتصادی: تولید و ذخیرهٔ منابع ---
    # «produces» = مقدار افزوده به تولید روزانه به‌ازای هر سطح
    # «cap_bonus» = مقدار افزوده به سقف ذخیره‌سازی به‌ازای هر سطح
    # «requires_port» = فقط قلعه/شهرهای دریایی می‌توانند بسازندش
    "lumber_mill": {"name": "چوب‌بری",     "cost": {"gold": 130, "stone": 30}, "hours": 4,  "type": "economy", "produces": {"wood": 9}},
    "stone_mine":  {"name": "معدن سنگ",   "cost": {"gold": 150, "wood": 60},  "hours": 4,  "type": "economy", "produces": {"stone": 8}},
    "iron_mine":   {"name": "معدن آهن",   "cost": {"gold": 200, "wood": 80},  "hours": 6,  "type": "economy", "produces": {"iron": 6}},
    "gold_mine":   {"name": "معدن طلا",   "cost": {"gold": 400, "stone": 100, "wood": 100}, "hours": 12, "type": "economy", "produces": {"gold": 12}},
    "market":      {"name": "بازار",       "cost": {"gold": 250, "wood": 70},  "hours": 6,  "type": "economy", "produces": {"gold": 3}},
    "treasury":    {"name": "خزانه",       "cost": {"gold": 300, "stone": 150, "iron": 40}, "hours": 8,  "type": "economy", "cap_bonus": {"gold": 40}},
    "farm":        {"name": "مزرعه",       "cost": {"gold": 100, "wood": 50},  "hours": 3,  "type": "economy", "produces": {"food": 10}},
    "ranch":       {"name": "دامداری",     "cost": {"gold": 150, "wood": 60},  "hours": 4,  "type": "economy", "produces": {"food": 6}},
    "winery":      {"name": "می‌کده",      "cost": {"gold": 220, "food": 60, "wood": 70}, "hours": 6,  "type": "economy", "produces": {"wine": 5}},
    "granary":     {"name": "انبار غله",   "cost": {"gold": 200, "stone": 50, "wood": 60}, "hours": 5,  "type": "economy", "cap_bonus": {"food": 40}},
    "warehouse":   {"name": "انبار",        "cost": {"gold": 200, "stone": 80, "wood": 50}, "hours": 5,  "type": "economy", "cap_bonus": {"stone": 15, "iron": 15}},

    # --- نظامی: پادگان هر یگان (پیش‌نیاز استخدام) ---
    "camp_sword":  {"name": "پادگان پیاده‌نظام",   "cost": {"gold": 250, "iron": 50,  "wood": 90},  "hours": 6,  "type": "barracks", "unit": "infantry"},
    "camp_spear":  {"name": "پادگان نیزه‌داران",   "cost": {"gold": 200, "iron": 30,  "wood": 70},  "hours": 5,  "type": "barracks", "unit": "spearman"},
    "camp_archer": {"name": "پادگان کمانداران",    "cost": {"gold": 200, "iron": 20,  "wood": 80},  "hours": 5,  "type": "barracks", "unit": "archer"},
    "camp_lcav":   {"name": "پادگان سوارهٔ سبک",   "cost": {"gold": 350, "iron": 60,  "wood": 110}, "hours": 8,  "type": "barracks", "unit": "light_cav"},
    "camp_hcav":   {"name": "پادگان سوارهٔ سنگین", "cost": {"gold": 500, "iron": 120, "wood": 140}, "hours": 12, "type": "barracks", "unit": "heavy_cav"},

    # --- نظامی: کارگاه تسلیحات هر یگان (منبع سلاح، پیش‌نیاز دوم استخدام) ---
    "armory_sword":  {"name": "کارگاه تسلیحات پیاده‌نظام",   "cost": {"gold": 200, "iron": 80,  "wood": 40}, "hours": 6,  "type": "armory", "unit": "infantry"},
    "armory_spear":  {"name": "کارگاه تسلیحات نیزه‌داران",   "cost": {"gold": 160, "iron": 60,  "wood": 40}, "hours": 5,  "type": "armory", "unit": "spearman"},
    "armory_archer": {"name": "کارگاه تسلیحات کمانداران",    "cost": {"gold": 160, "iron": 50,  "wood": 60}, "hours": 5,  "type": "armory", "unit": "archer"},
    "armory_lcav":   {"name": "کارگاه تسلیحات سوارهٔ سبک",   "cost": {"gold": 280, "iron": 100, "wood": 50}, "hours": 8,  "type": "armory", "unit": "light_cav"},
    "armory_hcav":   {"name": "کارگاه تسلیحات سوارهٔ سنگین", "cost": {"gold": 400, "iron": 180, "wood": 60}, "hours": 12, "type": "armory", "unit": "heavy_cav"},

    # --- دفاعی و زیرساخت ---
    "port":        {"name": "بندر",         "cost": {"gold": 600, "stone": 200, "wood": 260}, "hours": 12, "type": "defense", "requires_port": True},
    "wall":        {"name": "دیوار دفاعی", "cost": {"gold": 400, "stone": 300, "iron": 60},  "hours": 12, "type": "defense"},
    "watchtower":  {"name": "برج نگهبانی", "cost": {"gold": 250, "stone": 120, "wood": 70},  "hours": 7,  "type": "defense"},
}

# ---- قراردادهای سیاسی — شراب نقشی در بستن هر پیمان دارد ----
ALLIANCE_TYPES = {
    "non_aggression": {"name": "پیمان عدم‌تجاوز", "wine_cost": 20},
    "trade":          {"name": "پیمان تجاری",      "wine_cost": 30},
    "full_alliance":  {"name": "اتحاد کامل",       "wine_cost": 60},
}

# ---- سیستم ارتقای ساختمان‌ها ----
# دورهٔ بازی ۳۰ روزه است؛ هر ساختمان تا ۳۰ سطح ارتقا می‌خورد و هر سطح بالاتر
# هزینه و زمان بیشتری نسبت به سطح پایه می‌طلبد تا ارتقای کامل در طول یک دوره
# چالش‌برانگیز اما ممکن باشد.
# (LEVEL_HOURS_STEP=0.12 قبلاً یعنی جمع ساعتِ ۳۰ سطح ≈ ۸۲.۲× ساعت پایه — برای
# ساختمان‌های سنگین (پایه ≥۱۲ساعت) این از ۷۲۰ ساعتِ یک دورهٔ ۳۰روزه رد می‌شد و
# رساندن آن‌ها به سطح ۳۰ در یک دوره ریاضاً غیرممکن بود، برخلاف همین کامنت بالا)
MAX_BUILDING_LEVEL = 30
LEVEL_COST_STEP = 0.15   # هر سطح ~۱۵٪ هزینهٔ پایه اضافه می‌شود
LEVEL_HOURS_STEP = 0.06  # هر سطح ~۶٪ زمان پایه اضافه می‌شود

def building_cost(building_id: str, level: int) -> dict:
    """هزینهٔ ساخت/ارتقا به «level» (سطح ۱ = ساخت اولیه، هزینه = هزینهٔ پایه)"""
    base = BUILDINGS[building_id]["cost"]
    mult = 1 + (level - 1) * LEVEL_COST_STEP
    return {k: max(1, round(v * mult)) for k, v in base.items() if v}

def building_hours(building_id: str, level: int) -> float:
    base = BUILDINGS[building_id]["hours"]
    mult = 1 + (level - 1) * LEVEL_HOURS_STEP
    return round(base * mult, 1)

# ---- پیش‌نیاز اعزام هر نیروی عمومی: پادگان + کارگاه تسلیحات همان یگان ----
# نیروهای ویژهٔ اقلیمی (special) این پیش‌نیاز را ندارند — ساختمان مربوطه در بازی تعریف نشده
UNIT_REQUIREMENTS = {}
for _bid, _b in BUILDINGS.items():
    if _b.get("type") == "barracks":
        UNIT_REQUIREMENTS.setdefault(_b["unit"], {})["camp"] = _bid
    elif _b.get("type") == "armory":
        UNIT_REQUIREMENTS.setdefault(_b["unit"], {})["armory"] = _bid

def unit_requirements(troop_id: str):
    """(camp_building_id, armory_building_id) برای یک نیروی عمومی، یا None اگر نیرو ویژه/نامعتبر است"""
    req = UNIT_REQUIREMENTS.get(troop_id)
    if not req:
        return None
    return req.get("camp"), req.get("armory")

# ---- زمان سفر لشکر — بر مبنای فاصلهٔ اقلیمی، تقریبی روی محور شمال-جنوب نقشه ----
REGION_ORDER = {"north": 0, "vale": 1, "iron": 1, "river": 1, "west": 2, "crown": 2, "reach": 3, "storm": 3, "dorne": 4}
TRAVEL_SAME_REGION_MINUTES = 20
TRAVEL_CROSS_BASE_MINUTES = 40
TRAVEL_PER_HOP_MINUTES = 25

def travel_minutes(same_castle: bool, origin_region: str, target_region: str) -> int:
    """زمان رسیدن لشکر (دقیقه): همان قلعه = بی‌درنگ، همان اقلیم = کوتاه،
    اقلیم دیگر = پایه + فاصلهٔ اقلیمی روی محور شمال-جنوب"""
    if same_castle:
        return 0
    if origin_region == target_region:
        return TRAVEL_SAME_REGION_MINUTES
    hop = abs(REGION_ORDER.get(origin_region, 2) - REGION_ORDER.get(target_region, 2))
    return TRAVEL_CROSS_BASE_MINUTES + hop * TRAVEL_PER_HOP_MINUTES

# جاسوس‌ها سبک‌بارتر و سریع‌تر از لشکر حرکت می‌کنند — حدود نصف زمان یک لشکر کامل
SPY_SAME_REGION_MINUTES = 8
SPY_CROSS_BASE_MINUTES = 15
SPY_PER_HOP_MINUTES = 8

def spy_travel_minutes(origin_region: str, target_region: str) -> int:
    if origin_region == target_region:
        return SPY_SAME_REGION_MINUTES
    hop = abs(REGION_ORDER.get(origin_region, 2) - REGION_ORDER.get(target_region, 2))
    return SPY_CROSS_BASE_MINUTES + hop * SPY_PER_HOP_MINUTES

# --- بازار: کالاهایی که می‌شود کاروان فرستاد یا از بازار وستروس خرید (طلا خودش پول است، نه کالا) ---
TRADE_GOODS = ["wood", "stone", "iron", "food", "wine"]
TRADE_GOOD_NAMES = {"wood": "چوب", "stone": "سنگ", "iron": "آهن", "food": "غذا", "wine": "شراب"}
