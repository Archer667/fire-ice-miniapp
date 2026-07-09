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
    "stone_mine":  {"name": "معدن سنگ",   "cost": {"gold": 150}, "hours": 4,  "type": "economy", "produces": {"stone": 8}},
    "iron_mine":   {"name": "معدن آهن",   "cost": {"gold": 200}, "hours": 6,  "type": "economy", "produces": {"iron": 6}},
    "gold_mine":   {"name": "معدن طلا",   "cost": {"gold": 400, "stone": 100}, "hours": 12, "type": "economy", "produces": {"gold": 12}},
    "market":      {"name": "بازار",       "cost": {"gold": 250}, "hours": 6,  "type": "economy", "produces": {"gold": 3}},
    "treasury":    {"name": "خزانه",       "cost": {"gold": 300, "stone": 150}, "hours": 8,  "type": "economy", "cap_bonus": {"gold": 40}},
    "farm":        {"name": "مزرعه",       "cost": {"gold": 100}, "hours": 3,  "type": "economy", "produces": {"food": 10}},
    "ranch":       {"name": "دامداری",     "cost": {"gold": 150}, "hours": 4,  "type": "economy", "produces": {"food": 6}},
    "winery":      {"name": "می‌کده",      "cost": {"gold": 220, "food": 60}, "hours": 6,  "type": "economy", "produces": {"wine": 5}},
    "granary":     {"name": "انبار غله",   "cost": {"gold": 200, "stone": 50}, "hours": 5,  "type": "economy", "cap_bonus": {"food": 40}},
    "warehouse":   {"name": "انبار",        "cost": {"gold": 200, "stone": 80}, "hours": 5,  "type": "economy", "cap_bonus": {"stone": 15, "iron": 15}},

    # --- نظامی: پادگان هر یگان (پیش‌نیاز استخدام) ---
    "camp_sword":  {"name": "پادگان پیاده‌نظام",   "cost": {"gold": 250, "iron": 50},  "hours": 6,  "type": "barracks", "unit": "infantry"},
    "camp_spear":  {"name": "پادگان نیزه‌داران",   "cost": {"gold": 200, "iron": 30},  "hours": 5,  "type": "barracks", "unit": "spearman"},
    "camp_archer": {"name": "پادگان کمانداران",    "cost": {"gold": 200, "iron": 20},  "hours": 5,  "type": "barracks", "unit": "archer"},
    "camp_lcav":   {"name": "پادگان سوارهٔ سبک",   "cost": {"gold": 350, "iron": 60},  "hours": 8,  "type": "barracks", "unit": "light_cav"},
    "camp_hcav":   {"name": "پادگان سوارهٔ سنگین", "cost": {"gold": 500, "iron": 120}, "hours": 12, "type": "barracks", "unit": "heavy_cav"},

    # --- نظامی: کارگاه تسلیحات هر یگان (منبع سلاح، پیش‌نیاز دوم استخدام) ---
    "armory_sword":  {"name": "کارگاه تسلیحات پیاده‌نظام",   "cost": {"gold": 200, "iron": 80},  "hours": 6,  "type": "armory", "unit": "infantry"},
    "armory_spear":  {"name": "کارگاه تسلیحات نیزه‌داران",   "cost": {"gold": 160, "iron": 60},  "hours": 5,  "type": "armory", "unit": "spearman"},
    "armory_archer": {"name": "کارگاه تسلیحات کمانداران",    "cost": {"gold": 160, "iron": 50},  "hours": 5,  "type": "armory", "unit": "archer"},
    "armory_lcav":   {"name": "کارگاه تسلیحات سوارهٔ سبک",   "cost": {"gold": 280, "iron": 100}, "hours": 8,  "type": "armory", "unit": "light_cav"},
    "armory_hcav":   {"name": "کارگاه تسلیحات سوارهٔ سنگین", "cost": {"gold": 400, "iron": 180}, "hours": 12, "type": "armory", "unit": "heavy_cav"},

    # --- دفاعی و زیرساخت ---
    "port":        {"name": "بندر",         "cost": {"gold": 600, "stone": 200}, "hours": 16, "type": "defense"},
    "wall":        {"name": "دیوار دفاعی", "cost": {"gold": 400, "stone": 300}, "hours": 14, "type": "defense"},
    "watchtower":  {"name": "برج نگهبانی", "cost": {"gold": 250, "stone": 120}, "hours": 7,  "type": "defense"},
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
MAX_BUILDING_LEVEL = 30
LEVEL_COST_STEP = 0.15   # هر سطح ~۱۵٪ هزینهٔ پایه اضافه می‌شود
LEVEL_HOURS_STEP = 0.12  # هر سطح ~۱۲٪ زمان پایه اضافه می‌شود

def building_cost(building_id: str, level: int) -> dict:
    """هزینهٔ ساخت/ارتقا به «level» (سطح ۱ = ساخت اولیه، هزینه = هزینهٔ پایه)"""
    base = BUILDINGS[building_id]["cost"]
    mult = 1 + (level - 1) * LEVEL_COST_STEP
    return {k: max(1, round(v * mult)) for k, v in base.items() if v}

def building_hours(building_id: str, level: int) -> float:
    base = BUILDINGS[building_id]["hours"]
    mult = 1 + (level - 1) * LEVEL_HOURS_STEP
    return round(base * mult, 1)
