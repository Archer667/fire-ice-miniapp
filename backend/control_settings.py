"""تنظیمات زنده و نسخه‌دارِ قوانین بازی که فقط ادمین اصلی تغییر می‌دهد."""
from copy import deepcopy
import math

from config import (
    STARTING_RESOURCES, DAILY_PRODUCTION, RESOURCE_CAPS, TAX_RATE_DEFAULT,
    POPULARITY_START, FEAST_COST, FEAST_POPULARITY_GAIN, FEAST_COOLDOWN_HOURS,
    PRIVATE_ALLIANCE_MULTIPLIER, RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE,
    RUMOR_COOLDOWN_HOURS, SPY_GOLD_COST, SPY_MEN_COST, DAILY_REWARDS,
    SCORE_W_ECONOMY, SCORE_W_MILITARY, SCORE_W_POPULARITY, SCORE_W_ALLIANCE,
    TITLE_SCORE_BONUS,
)
from game_data import ALLIANCE_TYPES

DOC_ID = "control_center_v1"

DEFAULTS = {
    "tweets": {
        "gold_cost": RUMOR_GOLD_COST, "popularity_damage": RUMOR_POPULARITY_DAMAGE,
        "cooldown_hours": RUMOR_COOLDOWN_HOURS, "text_min": 10, "text_max": 400,
        "like_popularity": 0, "dislike_popularity": -1,
    },
    "economy": {
        "starting_resources": deepcopy(STARTING_RESOURCES),
        "daily_production": deepcopy(DAILY_PRODUCTION),
        "base_caps": deepcopy(RESOURCE_CAPS),
        "population_min_multiplier": .5, "population_max_multiplier": 1.5,
        "population_normal_popularity": POPULARITY_START,
    },
    "tax": {
        "default_rate": TAX_RATE_DEFAULT, "income_population_factor": 1.0,
        "income_min_multiplier": .5, "income_max_multiplier": 1.0,
        "safe_popularity": 50, "high_risk_popularity": 40, "guaranteed_popularity": 30,
        "overage_start": 20, "overage_step": 5, "overage_popularity_penalty": -1,
    },
    "diplomacy": {
        "pact_costs": {key: int(value.get("wine_cost", 0)) for key, value in ALLIANCE_TYPES.items()},
        "private_multiplier": PRIVATE_ALLIANCE_MULTIPLIER,
        "feast_food_cost": FEAST_COST["food"], "feast_wine_cost": FEAST_COST["wine"],
        "feast_popularity_gain": FEAST_POPULARITY_GAIN, "feast_cooldown_hours": FEAST_COOLDOWN_HOURS,
    },
    "war": {
        "minimum_army_men": 100, "minimum_ambush_men": 50, "roleplay_hours": 6,
        "report_visible_hours": 24, "cancel_penalty_percent": 50, "cancel_grace_minutes": 5,
        "spy_gold_cost": SPY_GOLD_COST, "spy_men_cost": SPY_MEN_COST,
    },
    "movement": {
        "base_speed_percent": 100, "route_time_percent": 100,
        "equipment_slowdown_cap_percent": 100,
        "commander_power_bonus_percent": 10, "commander_speed_bonus_percent": 10,
    },
    "scoring": {
        "building_economy": SCORE_W_ECONOMY, "building_military": SCORE_W_MILITARY,
        "popularity": SCORE_W_POPULARITY, "alliance": SCORE_W_ALLIANCE,
        "victory": 10, "defense": 10, "castle_capture": 15,
        "title_overlord": TITLE_SCORE_BONUS["overlord"],
        "title_warden": TITLE_SCORE_BONUS["warden"], "title_king": TITLE_SCORE_BONUS["king"],
    },
    "daily_rewards": {"rewards": deepcopy(DAILY_REWARDS), "reset_after_missed_days": 1},
    "medals": {
        "blood_and_steel": {"bronze": 3, "silver": 7, "gold": 10},
        "peaceful_warrior": {"bronze": 2, "silver": 5, "gold": 7},
        "conqueror": {"bronze": 1, "silver": 3, "gold": 6},
        "rich_father": {"bronze": 5000, "silver": 20000, "gold": 40000},
        "oathbound": {"bronze": 1, "silver": 3, "gold": 5},
        "eye_in_shadow": {"bronze": 2, "silver": 7, "gold": 10},
        "oath_loyal": {"bronze": 5, "silver": 10, "gold": 15},
    },
    "notifications": {
        key: {"bot": True, "raven": True, "admin_panel": True}
        for key in ("general", "tweet", "battle", "ambush", "rebellion", "diplomacy", "building", "trade", "daily", "roleplay", "espionage", "event")
    },
    "features": {key: True for key in ("war", "espionage", "tweets", "market", "caravans", "registration")},
}

SETTINGS = deepcopy(DEFAULTS)

def _deep_merge(base, incoming):
    out = deepcopy(base)
    if not isinstance(incoming, dict):
        return out
    for key, value in incoming.items():
        if key not in out:
            continue
        if isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        elif isinstance(out[key], list) and isinstance(value, list):
            out[key] = deepcopy(value)
        elif isinstance(value, (int, float, bool, str)):
            out[key] = value
    return out

def get(path: str, default=None):
    value = SETTINGS
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return deepcopy(value)

def snapshot() -> dict:
    return deepcopy(SETTINGS)

def feature_enabled(name: str) -> bool:
    return bool(get(f"features.{name}", True))

def notification_route(kind: str) -> dict:
    key = (kind or "general").lower()
    aliases = {
        "battle": ("battle", "war_"), "ambush": ("ambush",), "rebellion": ("rebellion",),
        "tweet": ("tweet", "rumor"), "diplomacy": ("alliance", "pact", "diplomacy"),
        "building": ("building",), "trade": ("trade", "caravan", "market"), "daily": ("daily",),
        "roleplay": ("roleplay",), "espionage": ("spy", "espionage"), "event": ("event",),
    }
    category = next((name for name, needles in aliases.items() if any(needle in key for needle in needles)), "general")
    return get(f"notifications.{category}", get("notifications.general", {"bot": True, "raven": True, "admin_panel": True}))

def replace(settings: dict):
    SETTINGS.clear()
    SETTINGS.update(_deep_merge(DEFAULTS, settings))
    return deepcopy(SETTINGS)

def validate(settings: dict) -> dict:
    clean = _deep_merge(DEFAULTS, settings)
    def finite_tree(value, path="settings"):
        if isinstance(value, dict):
            for key, child in value.items(): finite_tree(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value): finite_tree(child, f"{path}[{index}]")
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
            raise ValueError(f"{path} باید عدد معتبر باشد")
    finite_tree(clean)
    if int(clean["tweets"]["text_min"]) < 1 or int(clean["tweets"]["text_max"]) < int(clean["tweets"]["text_min"]):
        raise ValueError("حداکثر متن توییت باید از حداقل آن بیشتر باشد")
    guaranteed = int(clean["tax"]["guaranteed_popularity"]); high = int(clean["tax"]["high_risk_popularity"]); safe = int(clean["tax"]["safe_popularity"])
    if not 0 <= guaranteed < high < safe <= 100:
        raise ValueError("مرزهای محبوبیت باید به‌ترتیب شورش قطعی، خطر بالا و امن باشند")
    rewards = clean["daily_rewards"]["rewards"]
    if not isinstance(rewards, list) or len(rewards) != 7 or any(not isinstance(day, dict) for day in rewards):
        raise ValueError("جایزه روزانه باید دقیقاً هفت روز داشته باشد")
    for name, tiers in clean["medals"].items():
        if not 0 <= float(tiers["bronze"]) <= float(tiers["silver"]) <= float(tiers["gold"]):
            raise ValueError(f"شرط‌های مدال {name} باید از برنز تا طلا صعودی باشند")
    for section in ("economy", "diplomacy", "war", "movement", "daily_rewards"):
        def no_negative(value):
            if isinstance(value, dict):
                for child in value.values(): no_negative(child)
            elif isinstance(value, list):
                for child in value: no_negative(child)
            elif isinstance(value, (int, float)) and value < 0:
                raise ValueError(f"مقادیر بخش {section} نمی‌توانند منفی باشند")
        no_negative(clean[section])
    return clean

async def load():
    from db import game_settings
    doc = await game_settings.find_one({"_id": DOC_ID}) or {}
    return replace(doc.get("settings") or {})

async def save(settings: dict, *, user_id: int):
    from db import game_settings
    from game import now
    clean = validate(settings)
    replace(clean)
    await game_settings.update_one(
        {"_id": DOC_ID}, {"$set": {"settings": clean, "updated_at": now(), "updated_by": user_id}}, upsert=True,
    )
    return clean

async def reset(*, user_id: int):
    return await save(deepcopy(DEFAULTS), user_id=user_id)
