"""منطق مشترک: تولید روزانه، خرج منابع، ساخت‌وساز"""
from datetime import datetime, timezone, timedelta
from config import DAILY_PRODUCTION, RESOURCE_CAPS
from game_data import BUILDINGS

def now():
    """UTC naive — چون MongoDB هم datetime‌ها رو naive برمی‌گرداند، نگه‌داشتن هردو naive از خطای
    مقایسهٔ offset-naive/aware جلوگیری می‌کند."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _to_naive(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt

def _effect_totals(player: dict, suffix: str) -> dict:
    """جمع اثر تمام ساختمان‌های ساخته‌شده برای کلیدهایی با پسوند مشخص (مثلاً gold_pct یا food_cap)"""
    totals = {}
    for bid, built in player.get("buildings", {}).items():
        if not built:
            continue
        for key, val in BUILDINGS.get(bid, {}).get("effect", {}).items():
            if key.endswith(suffix):
                res = key[: -len(suffix)]
                totals[res] = totals.get(res, 0) + val
    return totals

def effective_rates(player: dict) -> dict:
    pct = _effect_totals(player, "_pct")
    return {k: base * (1 + pct.get(k, 0) / 100) for k, base in DAILY_PRODUCTION.items()}

def effective_caps(player: dict) -> dict:
    add = _effect_totals(player, "_cap")
    return {k: base + add.get(k, 0) for k, base in RESOURCE_CAPS.items()}

def apply_production(player: dict) -> dict:
    """تولید lazy: از آخرین آپدیت تا الان، روزانه حساب می‌شود — با احتساب اثر ساختمان‌ها"""
    last = _to_naive(player.get("last_tick", player["created_at"]))
    days = int((now() - last).total_seconds() // 86400)
    if days <= 0:
        return player
    res = player["resources"]
    rates = effective_rates(player)
    caps = effective_caps(player)
    for k, per_day in rates.items():
        res[k] = min(caps[k], res.get(k, 0) + per_day * days)
    player["last_tick"] = last.replace(microsecond=0) + timedelta(days=days)
    return player

def apply_construction(player: dict) -> bool:
    """اگر صف ساخت‌وساز به پایان رسیده باشد، ساختمان را تکمیل می‌کند. True یعنی چیزی تغییر کرد."""
    q = player.get("construction")
    if not q:
        return False
    if now() >= _to_naive(q["finishes_at"]):
        player.setdefault("buildings", {})[q["building_id"]] = True
        player["construction"] = None
        return True
    return False

def can_afford(resources: dict, cost: dict) -> bool:
    return all(resources.get(k, 0) >= v for k, v in cost.items())

def pay(resources: dict, cost: dict):
    for k, v in cost.items():
        resources[k] = resources.get(k, 0) - v
