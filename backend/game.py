"""منطق مشترک: تولید روزانه، خرج منابع"""
from datetime import datetime, timedelta
from config import (
    DAILY_PRODUCTION, RESOURCE_CAPS, TAX_RATE_DEFAULT,
    POPULARITY_START, tax_yield_multiplier,
)
from game_data import BUILDINGS, building_produces, building_cap_bonus

def now():
    # naive UTC — با چیزی که MongoDB برای فیلدهای datetime برمی‌گرداند یکی است.
    # اگر aware باشد، تفریق با مقداری که از دیتابیس خوانده شده (naive) خطای
    # TypeError می‌دهد.
    return datetime.utcnow()

def normalize_building_state(raw) -> dict:
    """buildings[id] معمولاً {"level","upgrade_to","ready_at"} است، اما نسخه‌های
    قدیمی‌تر بازی (پیش از سیستم سطح‌بندی) فقط True/False ذخیره می‌کردند —
    این را هم برای سازگاری با داده‌های قدیمی در دیتابیس می‌پذیریم."""
    if isinstance(raw, dict):
        return {"level": raw.get("level", 0), "upgrade_to": raw.get("upgrade_to"), "ready_at": raw.get("ready_at")}
    return {"level": 1, "upgrade_to": None, "ready_at": None} if raw else {"level": 0, "upgrade_to": None, "ready_at": None}

def resolve_building_upgrades(player: dict) -> dict:
    """ارتقاهای تمام‌شده را نهایی می‌کند و ساختار قدیمی‌تر (True/False به‌جای
    دیکشنری سطح‌دار) را که از نسخه‌های پیش از سیستم سطح‌بندی مانده، اصلاح می‌کند —
    هم برای قلعهٔ اصلی، هم برای هر قلعهٔ اضافه‌ای که این بازیکن (با فتح یا تصمیمِ
    ادمین) صاحبش شده"""
    resolve_building_upgrades_for(player.setdefault("buildings", {}))
    for state in player.get("castle_buildings", {}).values():
        resolve_building_upgrades_for(state)
    return player

def owned_castles(player: dict) -> list:
    """همهٔ قلعه‌های این بازیکن — قلعهٔ اصلی (خانه) + قلعه‌های اضافه‌ای که به‌عنوانِ
    غنیمتِ جنگ یا تصمیمِ ادمین گرفته (پایگاهِ دوم/سوم و...)"""
    out = [player["castle"]] if player.get("castle") else []
    out += [c for c in player.get("castle_buildings", {}) if c != player.get("castle")]
    return out

def castle_building_state(player: dict, castle: str) -> dict:
    """دیکشنریِ ساختمان‌های یک قلعهٔ مشخصِ این بازیکن — قلعهٔ اصلی از buildings،
    قلعه‌های اضافه از castle_buildings[castle]. اگر قلعه مالِ این بازیکن نباشه هم
    دیکشنریِ خالی برمی‌گردونه (چک مالکیت وظیفهٔ فراخوان‌کننده‌ست)"""
    if castle == player.get("castle"):
        return player.setdefault("buildings", {})
    return player.setdefault("castle_buildings", {}).setdefault(castle, {})

def building_levels_for(player: dict, castle: str):
    for bid, raw in castle_building_state(player, castle).items():
        level = normalize_building_state(raw)["level"]
        if level > 0 and bid in BUILDINGS:
            yield bid, level

def all_building_levels(player: dict) -> dict:
    """سطحِ هر ساختمان جمع‌شده روی همهٔ قلعه‌های این بازیکن — برای تولید/سقفِ کلی و
    امتیاز، چون خزانه و انبار یک کشورند نه هر قلعه جدا"""
    total = {}
    for castle in owned_castles(player):
        for bid, level in building_levels_for(player, castle):
            total[bid] = total.get(bid, 0) + level
    return total

def resolve_building_upgrades_for(state: dict) -> dict:
    """نسخهٔ خامِ resolve_building_upgrades که فقط روی یک دیکشنریِ ساختمانِ تکی
    (نه کلِ بازیکن) کار می‌کنه — برایِ همون قلعهٔ اصلی و هر قلعهٔ اضافه یکسان به کار می‌ره"""
    for bid, raw in list(state.items()):
        st = normalize_building_state(raw)
        ready = st["ready_at"]
        if ready and st["upgrade_to"]:
            if isinstance(ready, str):
                ready = datetime.fromisoformat(ready)
            if ready <= now():
                st["level"] = st["upgrade_to"]
                st["upgrade_to"] = None
                st["ready_at"] = None
        state[bid] = st
    return state

def effective_caps(player: dict) -> dict:
    caps = dict(RESOURCE_CAPS)
    for bid, level in all_building_levels(player).items():
        for k, v in building_cap_bonus(bid).items():
            caps[k] = caps.get(k, 0) + v * level
    return caps

def add_resources(player: dict, deltas: dict) -> dict:
    """مقدارهای مثبت رو به resources بازیکن اضافه می‌کنه، ولی هیچ‌وقت از سقفِ مؤثرش
    (بر پایهٔ ساختمان‌هاش) رد نمی‌شه — برخلافِ $inc خام تو مونگو که سقف رو کلاً نادیده
    می‌گیره. resources خودِ player رو درجا آپدیت و برش می‌گردونه (برای $set به دیتابیس)."""
    caps = effective_caps(player)
    res = player.setdefault("resources", {})
    for k, delta in deltas.items():
        if not delta:
            continue
        res[k] = min(caps.get(k, 10 ** 9), res.get(k, 0) + delta)
    return res

def daily_production(player: dict) -> dict:
    """تولید پایه + بونوس ساختمان‌ها (طبق مقادیرِ سراسریِ فعلی — پیش‌فرض یا بازنویسیِ
    ادمین) + مالیات (وابسته به جمعیت، نرخ و محبوبیت)"""
    prod = dict(DAILY_PRODUCTION)
    for bid, level in all_building_levels(player).items():
        for k, v in building_produces(bid).items():
            prod[k] = prod.get(k, 0) + v * level

    men = player["resources"].get("men", 0)
    tax_rate = max(0, min(100, int(player.get("tax_rate", TAX_RATE_DEFAULT))))
    multiplier = tax_yield_multiplier(player.get("popularity", POPULARITY_START))
    prod["gold"] = prod.get("gold", 0) + round(men * (tax_rate / 100) * multiplier)
    return prod

def apply_production(player: dict) -> dict:
    """تولید lazy: نرخ‌ها روزانه‌اند (بر اساس لولِ ساختمان)، ولی به‌نسبتِ زمانِ واقعاً
    گذشته (نه فقط روزهای کامل) اعمال می‌شوند — وگرنه بازیکن باید یک روزِ کامل صبر
    می‌کرد تا اولین‌بار عددی ببیند. برای این‌که تولیدِ کم‌مقدار (مثلاً چند واحد در روز)
    در چک‌های پیاپی صفر رند نشه و گم نشه، مقدارِ اعشاریِ دقیق نگه داشته می‌شود؛ فقط
    موقعِ نمایش (پاسخِ /me) برای بازیکن رند می‌شود"""
    last = player.get("last_tick", player["created_at"])
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    elapsed_days = (now() - last).total_seconds() / 86400
    if elapsed_days <= 0:
        return player
    res = player["resources"]
    caps = effective_caps(player)
    prod = daily_production(player)
    gold_before = res.get("gold", 0)
    for k, per_day in prod.items():
        res[k] = min(caps.get(k, 10 ** 9), res.get(k, 0) + per_day * elapsed_days)
    gold_added = max(0, res.get("gold", 0) - gold_before)
    if gold_added:
        stats = player.setdefault("stats", {})
        stats["gold_produced"] = stats.get("gold_produced", 0) + gold_added
    player["last_tick"] = now()
    return player

def can_afford(resources: dict, cost: dict) -> bool:
    return all(resources.get(k, 0) >= v for k, v in cost.items())

def pay(resources: dict, cost: dict):
    for k, v in cost.items():
        resources[k] = resources.get(k, 0) - v
