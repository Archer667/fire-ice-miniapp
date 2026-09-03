"""منطق مشترک: تولید روزانه، خرج منابع"""
from datetime import datetime, timedelta, timezone
from config import (
    DAILY_PRODUCTION, RESOURCE_CAPS, TAX_RATE_DEFAULT,
    POPULARITY_START, tax_yield_multiplier,
)
from game_data import BUILDINGS, building_produces, building_cap_bonus
from control_settings import get as rule

def now():
    # naive UTC — با چیزی که MongoDB برای فیلدهای datetime برمی‌گرداند یکی است.
    # اگر aware باشد، تفریق با مقداری که از دیتابیس خوانده شده (naive) خطای
    # TypeError می‌دهد.
    return datetime.utcnow()

def normalize_datetime(value) -> datetime | None:
    """تاریخ‌های قدیمیِ رشته‌ای و timezone-aware را به UTC بدون timezone تبدیل می‌کند."""
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

def normalize_building_state(raw) -> dict:
    """buildings[id] معمولاً {"level","upgrade_to","ready_at"} است، اما نسخه‌های
    قدیمی‌تر بازی (پیش از سیستم سطح‌بندی) فقط True/False ذخیره می‌کردند —
    این را هم برای سازگاری با داده‌های قدیمی در دیتابیس می‌پذیریم."""
    if isinstance(raw, dict):
        return {
            "level": max(0, int(raw.get("level", 0) or 0)),
            "upgrade_to": raw.get("upgrade_to"), "ready_at": raw.get("ready_at"),
            "notice_pending": raw.get("notice_pending"),
        }
    return {"level": 1, "upgrade_to": None, "ready_at": None, "notice_pending": None} if raw else {"level": 0, "upgrade_to": None, "ready_at": None, "notice_pending": None}

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

def resolve_building_upgrades_for(state: dict, at: datetime | None = None) -> dict:
    """نسخهٔ خامِ resolve_building_upgrades که فقط روی یک دیکشنریِ ساختمانِ تکی
    (نه کلِ بازیکن) کار می‌کنه — برایِ همون قلعهٔ اصلی و هر قلعهٔ اضافه یکسان به کار می‌ره"""
    current = normalize_datetime(at) or now()
    for bid, raw in list(state.items()):
        st = normalize_building_state(raw)
        ready = normalize_datetime(st["ready_at"])
        if ready and st["upgrade_to"]:
            st["ready_at"] = ready
            if ready <= current:
                completed_level = int(st["upgrade_to"])
                st["level"] = completed_level
                st["upgrade_to"] = None
                st["ready_at"] = None
                st["notice_pending"] = completed_level
        state[bid] = st
    return state

def effective_caps(player: dict) -> dict:
    caps = rule("economy.base_caps", RESOURCE_CAPS)
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

def _building_states(player: dict):
    yield player.setdefault("buildings", {})
    yield from player.setdefault("castle_buildings", {}).values()

def _apply_production_interval(player: dict, elapsed_days: float):
    if elapsed_days <= 0:
        return
    res = player["resources"]
    caps = effective_caps(player)
    prod = daily_production(player)
    gold_before = res.get("gold", 0)
    for key, per_day in prod.items():
        before = res.get(key, 0)
        candidate = before + per_day * elapsed_days
        cap = caps.get(key, 10 ** 9)
        # پایین‌آمدن سقف به‌دلیل تنظیم ادمین نباید موجودی قبلی را نابود کند؛ فقط
        # جلوی تولید تازه را می‌گیرد تا مصرف، مقدار را دوباره زیر سقف بیاورد.
        res[key] = max(before, min(cap, candidate)) if per_day >= 0 else candidate
    gold_added = max(0, res.get("gold", 0) - gold_before)
    if gold_added:
        stats = player.setdefault("stats", {})
        stats["gold_produced"] = stats.get("gold_produced", 0) + gold_added

def daily_production(player: dict) -> dict:
    """تولید پایه + بونوس ساختمان‌ها (طبق مقادیرِ سراسریِ فعلی — پیش‌فرض یا بازنویسیِ
    ادمین) + مالیات (وابسته به جمعیت، نرخ و محبوبیت)"""
    prod = rule("economy.daily_production", DAILY_PRODUCTION)
    for bid, level in all_building_levels(player).items():
        for k, v in building_produces(bid).items():
            prod[k] = prod.get(k, 0) + v * level

    # دهکده فقط ظرفیت جمعیت را زیاد می‌کند؛ سرعت رشد خود جمعیت تابع محبوبیت است.
    # محبوبیت ۵۰ = رشد عادی، صفر = نصف رشد و ۱۰۰ = یک‌ونیم برابر رشد.
    popularity = max(0, min(100, int(player.get("popularity", POPULARITY_START))))
    normal = max(1, float(rule("economy.population_normal_popularity", POPULARITY_START)))
    low = float(rule("economy.population_min_multiplier", .5))
    high = float(rule("economy.population_max_multiplier", 1.5))
    growth_multiplier = low + (high - low) * min(1, popularity / max(1, normal * 2))
    prod["men"] = round(prod.get("men", 0) * growth_multiplier, 2)

    men = player["resources"].get("men", 0)
    tax_rate = max(0, int(player.get("tax_rate", rule("tax.default_rate", TAX_RATE_DEFAULT))))
    pop_ratio = popularity / 100
    min_mult = float(rule("tax.income_min_multiplier", .5))
    max_mult = float(rule("tax.income_max_multiplier", 1.0))
    multiplier = min_mult + (max_mult - min_mult) * pop_ratio
    factor = max(0, float(rule("tax.income_population_factor", 1.0)))
    prod["gold"] = prod.get("gold", 0) + round(men * (tax_rate / 100) * multiplier * factor)
    return prod

def apply_production(player: dict) -> dict:
    """تولید lazy: نرخ‌ها روزانه‌اند (بر اساس لولِ ساختمان)، ولی به‌نسبتِ زمانِ واقعاً
    گذشته (نه فقط روزهای کامل) اعمال می‌شوند — وگرنه بازیکن باید یک روزِ کامل صبر
    می‌کرد تا اولین‌بار عددی ببیند. برای این‌که تولیدِ کم‌مقدار (مثلاً چند واحد در روز)
    در چک‌های پیاپی صفر رند نشه و گم نشه، مقدارِ اعشاریِ دقیق نگه داشته می‌شود؛ فقط
    موقعِ نمایش (پاسخِ /me) برای بازیکن رند می‌شود"""
    current = now()
    last = normalize_datetime(player.get("last_tick", player["created_at"]))
    if not last or current <= last:
        resolve_building_upgrades(player)
        player["last_tick"] = last or current
        return player

    # ارتقاهایی که پیش از آخرین tick تمام شده‌اند، از ابتدای بازه فعال‌اند.
    for state in _building_states(player):
        resolve_building_upgrades_for(state, last)

    boundaries = set()
    for state in _building_states(player):
        for raw in state.values():
            st = normalize_building_state(raw)
            ready = normalize_datetime(st.get("ready_at"))
            if st.get("upgrade_to") and ready and last < ready <= current:
                boundaries.add(ready)

    cursor = last
    for boundary in sorted(boundaries):
        _apply_production_interval(player, (boundary - cursor).total_seconds() / 86400)
        for state in _building_states(player):
            resolve_building_upgrades_for(state, boundary)
        cursor = boundary

    _apply_production_interval(player, (current - cursor).total_seconds() / 86400)
    for state in _building_states(player):
        resolve_building_upgrades_for(state, current)
    player["last_tick"] = current
    return player

def production_fields(player: dict) -> dict:
    """تمام فیلدهایی که apply_production ممکن است تغییر دهد.

    هر مسیری که تولید را تسویه می‌کند باید این مجموعه را یک‌جا ذخیره کند؛ در غیر این
    صورت ممکن است منابع ثبت شوند ولی تکمیل ساختمان/آمار تولید از دست برود، یا برعکس.
    """
    return {
        "resources": player["resources"],
        "last_tick": player["last_tick"],
        "stats": player.get("stats", {}),
        "buildings": player.get("buildings", {}),
        "castle_buildings": player.get("castle_buildings", {}),
    }

def can_afford(resources: dict, cost: dict) -> bool:
    return all(resources.get(k, 0) >= v for k, v in cost.items())

def pay(resources: dict, cost: dict):
    for k, v in cost.items():
        resources[k] = resources.get(k, 0) - v
