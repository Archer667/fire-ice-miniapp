"""Medal definitions and helpers shared by player/admin APIs."""

from db import players

TIER_ORDER = {"bronze": 1, "silver": 2, "gold": 3}

MEDALS = {
    "blood_and_steel": {
        "name": "خون و فولاد", "icon": "⚔️", "stat": "attack_wins",
        "thresholds": {"bronze": 3, "silver": 7, "gold": 10},
        "titles": {"bronze": "شمشیرآزموده", "silver": "خون‌دیده", "gold": "سالار میدان"},
    },
    "peaceful_warrior": {
        "name": "صلح‌طلب، ولی جنگ بلده", "icon": "🛡️", "stat": "defense_wins",
        "thresholds": {"bronze": 2, "silver": 5, "gold": 7},
        "titles": {"bronze": "پاسدار آرامش", "silver": "سپر صلح", "gold": "صلح‌بان شکست‌ناپذیر"},
    },
    "conqueror": {
        "name": "فاتح", "icon": "🏰", "stat": "castles_captured",
        "thresholds": {"bronze": 1, "silver": 3, "gold": 6},
        "titles": {"bronze": "قلعه‌گشا", "silver": "پرچم‌افراز", "gold": "فاتح شش دژ"},
    },
    "rich_father": {
        "name": "پدر پولدار", "icon": "🪙", "stat": "gold_produced",
        "thresholds": {"bronze": 5000, "silver": 20000, "gold": 40000},
        "titles": {"bronze": "سکه‌شمار", "silver": "خزانه‌دار بزرگ", "gold": "پدر زر"},
    },
    "oathbound": {
        "name": "سوگنددار", "icon": "🤝", "stat": "alliances_accepted",
        "thresholds": {"bronze": 1, "silver": 3, "gold": 5},
        "titles": {"bronze": "هم‌پیمان", "silver": "حافظ سوگند", "gold": "سوگنددار بزرگ"},
    },
    "eye_in_shadow": {
        "name": "چشم در سایه", "icon": "👁️", "stat": "successful_spies",
        "thresholds": {"bronze": 2, "silver": 7, "gold": 10},
        "titles": {"bronze": "نجواشنو", "silver": "سایه‌رو", "gold": "چشم پنهان قلمرو"},
    },
    "realm_storyteller": {
        "name": "راوی قلمرو", "icon": "📜", "manual": True,
        "titles": {"bronze": "قصه‌گو", "silver": "وقایع‌نگار", "gold": "زبان تاریخ"},
    },
    "oath_loyal": {
        "name": "وفادار به عهد", "icon": "🔥", "stat": "best_daily_streak",
        "thresholds": {"bronze": 5, "silver": 10, "gold": 15},
        "titles": {"bronze": "هم‌عهد", "silver": "وفادار دیرین", "gold": "نگهبان عهد"},
    },
}

STAT_DEFAULTS = {
    "attack_wins": 0, "defense_wins": 0, "castles_captured": 0,
    "gold_produced": 0, "alliances_accepted": 0,
    "alliances_7_days": 0, "alliances_10_days": 0,
    "successful_spies": 0, "best_daily_streak": 0,
}


def normalize_stats(player):
    stats = dict(player.get("stats") or {})
    for key, value in STAT_DEFAULTS.items():
        stats.setdefault(key, value)
    player["stats"] = stats
    return stats


def _automatic_tier(key, stats):
    definition = MEDALS[key]
    if key == "oathbound":
        if stats.get("alliances_10_days", 0) >= 5:
            return "gold"
        if stats.get("alliances_accepted", 0) >= 3:
            return "silver"
        if stats.get("alliances_7_days", 0) >= 1:
            return "bronze"
        return None
    value = stats.get(definition["stat"], 0)
    earned = None
    for tier in ("bronze", "silver", "gold"):
        if value >= definition["thresholds"][tier]:
            earned = tier
    return earned


def sync_medals(player):
    stats = normalize_stats(player)
    medals = dict(player.get("medals") or {})
    for key, definition in MEDALS.items():
        if definition.get("manual"):
            continue
        tier = _automatic_tier(key, stats)
        current = medals.get(key)
        current_tier = current.get("tier") if isinstance(current, dict) else current
        if tier and TIER_ORDER[tier] > TIER_ORDER.get(current_tier, 0):
            medals[key] = {"tier": tier}
    player["medals"] = medals
    return medals


def medal_rows(player):
    medals = sync_medals(player)
    rows = []
    for key, value in medals.items():
        definition = MEDALS.get(key)
        if not definition:
            continue
        tier = value.get("tier") if isinstance(value, dict) else value
        if tier not in TIER_ORDER:
            continue
        rows.append({
            "key": key, "name": definition["name"], "icon": definition["icon"],
            "tier": tier, "title": definition["titles"][tier],
        })
    return sorted(rows, key=lambda row: (-TIER_ORDER[row["tier"]], row["name"]))


async def bump_player_stat(tg_id, key, amount=1):
    if key not in STAT_DEFAULTS:
        raise ValueError("unknown medal stat")
    await players.update_one({"tg_id": tg_id}, {"$inc": {f"stats.{key}": amount}})
    player = await players.find_one({"tg_id": tg_id})
    if not player:
        return None
    medals_before = dict(player.get("medals") or {})
    medals = sync_medals(player)
    if medals != medals_before:
        await players.update_one({"tg_id": tg_id}, {"$set": {"medals": medals}})
    return player
