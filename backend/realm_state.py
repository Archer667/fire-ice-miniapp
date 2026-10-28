"""Shared political and economic state for the realm.

The game runs on a standalone MongoDB instance, so cross-document changes use
idempotent receipts instead of assuming replica-set transactions are available.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import POPULARITY_START, tax_yield_multiplier
from db import db, players
from game import now, all_building_levels, effective_caps


EVENTS = db.game_events
POPULARITY_EVENTS = db.popularity_events
REPUTATION = db.political_reputation

INFLUENCE_START = 20


def clamp(value: int | float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(round(value))))


async def record_event(
    kind: str,
    title: str,
    *,
    actor_id: int | None = None,
    target_ids: list[int] | None = None,
    detail: str = "",
    visibility: str = "participants",
    data: dict | None = None,
    dedupe_key: str | None = None,
):
    event_id = dedupe_key or str(uuid4())
    doc = {
        "_id": event_id,
        "kind": kind,
        "title": title[:160],
        "detail": detail[:2000],
        "actor_id": actor_id,
        "target_ids": list(dict.fromkeys(target_ids or [])),
        "visibility": visibility,
        "data": data or {},
        "game_at": now(),
        "real_at": datetime.now(timezone.utc),
    }
    try:
        await EVENTS.insert_one(doc)
    except DuplicateKeyError:
        return await EVENTS.find_one({"_id": event_id})
    return doc


async def adjust_popularity(
    tg_id: int,
    delta: int,
    reason: str,
    *,
    source_kind: str = "system",
    source_id: str | None = None,
    actor_id: int | None = None,
):
    """Apply one clamped popularity change and keep a complete, searchable trail."""
    if not delta:
        player = await players.find_one({"tg_id": tg_id}, {"popularity": 1})
        return clamp((player or {}).get("popularity", POPULARITY_START))
    for _ in range(4):
        player = await players.find_one({"tg_id": tg_id}, {"popularity": 1, "name": 1})
        if not player:
            return None
        before = clamp(player.get("popularity", POPULARITY_START))
        after = clamp(before + delta)
        applied = after - before
        result = await players.update_one(
            {"tg_id": tg_id, "popularity": player.get("popularity", {"$exists": False})},
            {"$set": {"popularity": after}},
        )
        if result.matched_count:
            event = {
                "tg_id": tg_id,
                "player_name": player.get("name", ""),
                "before": before,
                "after": after,
                "delta": applied,
                "reason": reason[:300],
                "source_kind": source_kind,
                "source_id": source_id,
                "actor_id": actor_id,
                "game_at": now(),
                "real_at": datetime.now(timezone.utc),
            }
            await POPULARITY_EVENTS.insert_one(event)
            await record_event(
                "popularity",
                "تغییر محبوبیت",
                actor_id=actor_id,
                target_ids=[tg_id],
                detail=reason,
                data={"before": before, "after": after, "delta": applied, "source": source_kind},
                dedupe_key=(f"popularity:{source_kind}:{source_id}:{tg_id}" if source_id else None),
            )
            return after
    raise RuntimeError("popularity update contention")


async def adjust_influence(tg_id: int, delta: int, reason: str, *, source_id: str | None = None):
    from hashlib import sha256
    from realm_controls import rules, reward_for
    cfg = await rules()
    delta = reward_for(source_id or '', delta, cfg)
    for _ in range(8):
        player = await players.find_one({'tg_id': tg_id})
        if not player:
            return None
        character = str(player.get('created_at', 'legacy'))
        key = sha256((character + ':' + (source_id or str(uuid4()))).encode()).hexdigest()
        field = 'influence_receipts.' + key
        receipt = player.get('influence_receipts', {}).get(key)
        if receipt:
            await record_event('influence', 'تغییر نفوذ سیاسی', target_ids=[tg_id], detail=receipt['reason'],
                               data=receipt, dedupe_key='influence:' + key + ':' + str(tg_id))
            return receipt['balance']
        before = int(player.get('political_influence', cfg['influence_start']))
        after = before + delta if delta <= 0 else before + min(delta, max(0, cfg['influence_cap'] - before))
        if after < 0:
            return None
        receipt = {'before': before, 'balance': after, 'delta': after-before, 'reason': reason[:500],
                   'source_id': source_id, 'at': datetime.now(timezone.utc), 'character': character}
        query = {'_id': player['_id'], field: {'$exists': False},
                 'political_influence': player.get('political_influence', {'$exists': False})}
        result = await players.update_one(query, {'$set': {'political_influence': after, field: receipt}})
        if result.matched_count:
            await record_event('influence', 'تغییر نفوذ سیاسی', target_ids=[tg_id], detail=reason,
                               data=receipt, dedupe_key='influence:' + key + ':' + str(tg_id))
            return after
    raise RuntimeError('influence update contention')


async def adjust_reputation(actor_id: int, target_id: int, delta: int, reason: str, *, source_id: str | None = None):
    if actor_id == target_id or not delta:
        return None
    identity = f"{actor_id}:{target_id}"
    row = await REPUTATION.find_one({"_id": identity}) or {"score": 0}
    before = clamp(row.get("score", 0), -100, 100)
    after = clamp(before + delta, -100, 100)
    await REPUTATION.update_one(
        {"_id": identity},
        {"$set": {"from_id": actor_id, "to_id": target_id, "score": after, "updated_at": now()},
         "$push": {"history": {"$each": [{"at": now(), "delta": after - before, "reason": reason[:240], "source_id": source_id}], "$slice": -80}}},
        upsert=True,
    )
    return after


def popularity_band(value: int) -> dict:
    value = clamp(value)
    if value >= 80:
        return {"id": "devoted", "label": "وفادار", "color": "gold"}
    if value >= 60:
        return {"id": "stable", "label": "آرام", "color": "green"}
    if value >= 40:
        return {"id": "uneasy", "label": "ناآرام", "color": "amber"}
    if value >= 20:
        return {"id": "angry", "label": "خشمگین", "color": "red"}
    return {"id": "revolt", "label": "در آستانهٔ شورش", "color": "crimson"}


async def prosperity(player: dict) -> dict:
    resources = player.get("resources", {})
    caps = effective_caps(player) if (player.get("castle") or player.get("castle_buildings")) else {}
    food_cap = max(1, float(caps.get("food", 1)))
    food_ratio = max(0, min(1, float(resources.get("food", 0)) / food_cap))
    building_levels = sum(all_building_levels(player).values())
    stats = player.get("stats", {})
    produced = float(stats.get("gold_produced", 0) or 0)
    traded = float(stats.get("market_bought_value", 0) or 0) + float(stats.get("market_sold_value", 0) or 0)
    fulfilled = int(stats.get("supply_deliveries", 0) or 0)
    missed = int(stats.get("supply_breaches", 0) or 0)
    factors = {
        "زیرساخت": min(25, building_levels * 2),
        "ذخیرهٔ غذا": round(food_ratio * 20),
        "تولید ثبت‌شده": min(20, round(produced / 500)),
        "گردش بازار": min(25, round(traded / 1000)),
        "تعهدهای تجاری": max(-15, min(10, fulfilled * 2 - missed * 5)),
    }
    score = clamp(20 + sum(factors.values()))
    return {"score": score, "factors": factors, "label": "رونق بالا" if score >= 75 else "رو به رشد" if score >= 55 else "متعادل" if score >= 35 else "رکود"}


async def overview_for(player: dict) -> dict:
    from realm_controls import rules
    cfg = await rules()
    popularity = clamp(player.get("popularity", POPULARITY_START))
    pop_events = []
    async for row in POPULARITY_EVENTS.find({"tg_id": player["tg_id"]}).sort("game_at", -1).limit(12):
        pop_events.append({
            "at": row["game_at"].isoformat(), "delta": row.get("delta", 0),
            "before": row.get("before"), "after": row.get("after"), "reason": row.get("reason", ""),
        })
    return {
        "popularity": popularity,
        "popularity_band": popularity_band(popularity),
        "popularity_effects": {
            "tax_yield_percent": round(tax_yield_multiplier(popularity) * 100),
            "population_growth_percent": round((.5 + popularity / 100) * 100),
        },
        "popularity_history": pop_events,
        "influence": int(player.get("political_influence", cfg["influence_start"])),
        "prosperity": await prosperity(player),
    }


async def migrate_players():
    from realm_controls import rules
    initial = (await rules())["influence_start"]
    await players.update_many({"political_influence": {"$exists": False}}, {"$set": {"political_influence": initial}})


async def ensure_indexes():
    specs = [
        (EVENTS, [("game_at", -1)]),
        (EVENTS, [("actor_id", 1), ("game_at", -1)]),
        (EVENTS, [("target_ids", 1), ("game_at", -1)]),
        (POPULARITY_EVENTS, [("tg_id", 1), ("game_at", -1)]),
        (REPUTATION, [("from_id", 1), ("score", -1)]),
    ]
    for collection, keys in specs:
        await collection.create_index(keys)
