from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players
from game import now, apply_production, can_afford, pay, normalize_building_state, resolve_building_upgrades
from game_data import BUILDINGS, MAX_BUILDING_LEVEL, building_cost, building_hours

router = APIRouter(prefix="/api/buildings", tags=["buildings"])

EMPTY_STATE = {"level": 0, "upgrade_to": None, "ready_at": None}
_resolve = resolve_building_upgrades

@router.get("")
async def list_buildings(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = _resolve(p)
    await players.update_one({"tg_id": user["id"]}, {"$set": {"buildings": p["buildings"]}})

    out = []
    for bid, meta in BUILDINGS.items():
        st = p["buildings"].get(bid, EMPTY_STATE)
        level = st["level"]
        target = st["upgrade_to"] or (level + 1 if level < MAX_BUILDING_LEVEL else None)
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "unit": meta.get("unit"), "requires_port": meta.get("requires_port", False),
            "level": level, "max_level": MAX_BUILDING_LEVEL,
            "upgrading": bool(st["upgrade_to"]),
            "ready_at": st["ready_at"].isoformat() if st.get("ready_at") else None,
            "next_level": target,
            "next_cost": building_cost(bid, target) if target else None,
            "next_hours": building_hours(bid, target) if target else None,
        })
    return out

class ActionBody(BaseModel):
    building_id: str

async def _start_upgrade(building_id: str, user: dict, require_built: bool):
    if building_id not in BUILDINGS:
        raise HTTPException(400, "ساختمان نامعتبر")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)
    p = _resolve(p)

    st = dict(p["buildings"].get(building_id, EMPTY_STATE))
    if st["upgrade_to"]:
        raise HTTPException(400, "این ساختمان هم‌اکنون در حال ساخت است")
    if require_built and st["level"] == 0:
        raise HTTPException(400, "اول این ساختمان را بنا کن")
    if not require_built and st["level"] > 0:
        raise HTTPException(400, "این ساختمان قبلاً بنا شده — آن را ارتقا بده")
    if st["level"] >= MAX_BUILDING_LEVEL:
        raise HTTPException(400, "این ساختمان به بیشینهٔ سطح رسیده")
    if not require_built and BUILDINGS[building_id].get("requires_port") and not p.get("is_port"):
        raise HTTPException(400, "این ساختمان فقط در قلعه/شهرهای دریایی و بندری ساخته می‌شود")

    target = st["level"] + 1
    cost = building_cost(building_id, target)
    hours = building_hours(building_id, target)
    if not can_afford(p["resources"], cost):
        raise HTTPException(400, "منابع کافی نیست")

    pay(p["resources"], cost)
    st["upgrade_to"] = target
    st["ready_at"] = now() + timedelta(hours=hours)
    p["buildings"][building_id] = st

    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": p["resources"], "buildings": p["buildings"], "last_tick": p["last_tick"],
    }})
    return {"ok": True, "target_level": target, "cost": cost, "ready_at": st["ready_at"].isoformat()}

@router.post("/build")
async def build(body: ActionBody, user: dict = Depends(get_user)):
    return await _start_upgrade(body.building_id, user, require_built=False)

@router.post("/upgrade")
async def upgrade(body: ActionBody, user: dict = Depends(get_user)):
    return await _start_upgrade(body.building_id, user, require_built=True)
