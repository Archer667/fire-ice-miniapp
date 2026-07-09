"""منطق مشترک: تولید روزانه، خرج منابع"""
from datetime import datetime
from config import DAILY_PRODUCTION, RESOURCE_CAPS

def now():
    # naive UTC — با چیزی که MongoDB برای فیلدهای datetime برمی‌گرداند یکی است.
    # اگر aware باشد، تفریق با مقداری که از دیتابیس خوانده شده (naive) خطای
    # TypeError می‌دهد.
    return datetime.utcnow()

def apply_production(player: dict) -> dict:
    """تولید lazy: از آخرین آپدیت تا الان، روزانه حساب می‌شود"""
    last = player.get("last_tick", player["created_at"])
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    days = int((now() - last).total_seconds() // 86400)
    if days <= 0:
        return player
    res = player["resources"]
    for k, per_day in DAILY_PRODUCTION.items():
        res[k] = min(RESOURCE_CAPS[k], res.get(k, 0) + per_day * days)
    player["last_tick"] = last.replace(microsecond=0) + __import__("datetime").timedelta(days=days)
    return player

def can_afford(resources: dict, cost: dict) -> bool:
    return all(resources.get(k, 0) >= v for k, v in cost.items())

def pay(resources: dict, cost: dict):
    for k, v in cost.items():
        resources[k] = resources.get(k, 0) - v
