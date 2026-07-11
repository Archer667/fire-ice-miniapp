import random
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, spy_missions
from game import now, can_afford, pay, normalize_building_state
from game_data import BUILDINGS, spy_travel_minutes
from routers.war import OP_TYPES
from routers.ravens import send_system_message
from config import SPY_GOLD_COST, SPY_MEN_COST, SPY_BASE_CHANCE, SPY_MIN_CHANCE, SPY_CHANCE_PER_WATCHTOWER

router = APIRouter(prefix="/api/espionage", tags=["espionage"])

class SpyBody(BaseModel):
    target_castle: str

def _building_levels(player: dict) -> dict:
    out = {}
    for bid, raw in player.get("buildings", {}).items():
        lvl = normalize_building_state(raw)["level"]
        if lvl > 0:
            out[bid] = lvl
    return out

async def resolve_spy_missions(tg_id: int, resources: dict) -> dict:
    """تیک تنبل: ماموریت‌های رسیده را می‌بندد — موفق: جاسوس‌ها برمی‌گردند،
    ناموفق: به قلعهٔ هدف کلاغِ «جاسوس دستگیر شد» فرستاده می‌شود"""
    cur = spy_missions.find({"tg_id": tg_id, "delivered": False})
    async for m in cur:
        if now() < m["arrival_at"]:
            continue
        if m["success"]:
            resources["men"] = resources.get("men", 0) + m["men_sent"]
        else:
            target = await players.find_one({"tg_id": m["target_tg_id"]})
            if target:
                await send_system_message(
                    target["tg_id"], target["name"],
                    f"جاسوسی از سوی {m['player_name']} در تلاش برای نفوذ به {m['target_castle']} شناسایی و دستگیر شد.",
                )
        await spy_missions.update_one({"_id": m["_id"]}, {"$set": {"delivered": True}})
    return resources

@router.post("/send")
async def send(body: SpyBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p["resources"] = await resolve_spy_missions(user["id"], p["resources"])

    target = await players.find_one({"castle": body.target_castle})
    if not target:
        raise HTTPException(404, "این قلعه صاحبی ندارد که جاسوسی‌اش کنی")
    if target["tg_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی جاسوس به قلعهٔ خودت بفرستی")

    if not can_afford(p["resources"], {"gold": SPY_GOLD_COST}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < SPY_MEN_COST:
        raise HTTPException(400, "نفرات کافی نداری")

    pay(p["resources"], {"gold": SPY_GOLD_COST})
    p["resources"]["men"] -= SPY_MEN_COST
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    travel = spy_travel_minutes(p["region"], target["region"])
    arrival_at = now() + timedelta(minutes=travel)

    watchtower_level = _building_levels(target).get("watchtower", 0)
    chance = max(SPY_MIN_CHANCE, SPY_BASE_CHANCE - watchtower_level * SPY_CHANCE_PER_WATCHTOWER)
    success = random.random() * 100 < chance

    report = None
    if success:
        levels = _building_levels(target)
        military = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                    for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") in ("barracks", "armory")]
        defense = [{"name": BUILDINGS[bid]["name"], "level": lvl}
                   for bid, lvl in levels.items() if BUILDINGS.get(bid, {}).get("type") == "defense"]
        camps = []
        async for c in campaigns.find({"tg_id": target["tg_id"], "active": True}):
            camps.append({
                "op_type": c["op_type"], "op_name": OP_TYPES.get(c["op_type"], {}).get("name", c["op_type"]),
                "origin": c["origin_castle"], "target": c["target_castle"],
                "men_committed": c["men_committed"],
                "arrived": now() >= c.get("arrival_at", now()),
            })
        report = {"resources": target["resources"], "military": military, "defense": defense, "campaigns": camps}

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": p["castle"], "target_castle": body.target_castle, "target_tg_id": target["tg_id"],
        "gold_cost": SPY_GOLD_COST, "men_sent": SPY_MEN_COST,
        "travel_minutes": travel, "arrival_at": arrival_at,
        "success": success, "report": report, "delivered": False,
        "created_at": now(),
    }
    res = await spy_missions.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "travel_minutes": travel}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    cur = spy_missions.find({"tg_id": user["id"]}).sort("created_at", -1).limit(30)
    out = []
    async for m in cur:
        arrived = now() >= m["arrival_at"]
        out.append({
            "id": str(m["_id"]), "target": m["target_castle"],
            "travel_minutes": m["travel_minutes"], "arrived": arrived,
            "success": m["success"] if arrived else None,
            "report": m["report"] if arrived and m["success"] else None,
            "created_at": m["created_at"].isoformat(),
        })
    return out
