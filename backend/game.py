"""منطق مشترک: تولید روزانه، خرج منابع"""
from datetime import datetime, timedelta
from config import (
    DAILY_PRODUCTION, RESOURCE_CAPS, TAX_RATE_DEFAULT,
    POPULARITY_START, max_tax_rate, tax_yield_multiplier,
)
from game_data import BUILDINGS

def now():
    # naive UTC — با چیزی که MongoDB برای فیلدهای datetime برمی‌گرداند یکی است.
    # اگر aware باشد، تفریق با مقداری که از دیتابیس خوانده شده (naive) خطای
    # TypeError می‌دهد.
    return datetime.utcnow()

def _building_levels(player: dict):
    for bid, st in player.get("buildings", {}).items():
        level = st.get("level", 0)
        if level > 0 and bid in BUILDINGS:
            yield bid, level

def effective_caps(player: dict) -> dict:
    caps = dict(RESOURCE_CAPS)
    for bid, level in _building_levels(player):
        for k, v in BUILDINGS[bid].get("cap_bonus", {}).items():
            caps[k] = caps.get(k, 0) + v * level
    return caps

def daily_production(player: dict) -> dict:
    """تولید پایه + بونوس ساختمان‌ها + مالیات (وابسته به جمعیت، نرخ و محبوبیت)"""
    prod = dict(DAILY_PRODUCTION)
    for bid, level in _building_levels(player):
        for k, v in BUILDINGS[bid].get("produces", {}).items():
            prod[k] = prod.get(k, 0) + v * level

    men = player["resources"].get("men", 0)
    tax_rate = min(player.get("tax_rate", TAX_RATE_DEFAULT), max_tax_rate(player.get("popularity", POPULARITY_START)))
    multiplier = tax_yield_multiplier(player.get("popularity", POPULARITY_START))
    prod["gold"] = prod.get("gold", 0) + round(men * (tax_rate / 100) * multiplier)
    return prod

def apply_production(player: dict) -> dict:
    """تولید lazy: از آخرین آپدیت تا الان، روزانه حساب می‌شود"""
    last = player.get("last_tick", player["created_at"])
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    days = int((now() - last).total_seconds() // 86400)
    if days <= 0:
        return player
    res = player["resources"]
    caps = effective_caps(player)
    prod = daily_production(player)
    for k, per_day in prod.items():
        res[k] = min(caps.get(k, 10 ** 9), res.get(k, 0) + per_day * days)
    player["last_tick"] = last.replace(microsecond=0) + timedelta(days=days)
    return player

def can_afford(resources: dict, cost: dict) -> bool:
    return all(resources.get(k, 0) >= v for k, v in cost.items())

def pay(resources: dict, cost: dict):
    for k, v in cost.items():
        resources[k] = resources.get(k, 0) - v
