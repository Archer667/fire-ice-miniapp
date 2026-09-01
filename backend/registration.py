from db import game_settings, map_castles, players
from game_data import REGIONS

SETTINGS_ID = "registration_capacity"
DEFAULT_CAPACITY = 5


async def castle_region_map():
    out = {
        castle: region_id
        for region_id, region in REGIONS.items()
        for castle in [*region.get("castles", []), *region.get("ports", [])]
    }
    async for row in map_castles.find({}, {"name": 1, "region": 1}):
        if row.get("name") and row.get("region") in REGIONS:
            out[row["name"]] = row["region"]
    return out


async def registration_state():
    saved = await game_settings.find_one({"_id": SETTINGS_ID}) or {}
    raw = saved.get("capacities", {})
    capacities = {key: max(0, min(250, int(raw.get(key, DEFAULT_CAPACITY)))) for key in REGIONS}
    counts = {key: 0 for key in REGIONS}
    pipeline = [
        {"$match": {"region": {"$in": list(REGIONS)}, "castle": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$region", "count": {"$sum": 1}}},
    ]
    async for row in players.aggregate(pipeline):
        counts[row["_id"]] = int(row["count"])
    return {
        key: {
            "id": key, "name": REGIONS[key]["name"], "capacity": capacities[key],
            "assigned": counts[key], "remaining": max(0, capacities[key] - counts[key]),
            "full": counts[key] >= capacities[key],
        }
        for key in REGIONS
    }
