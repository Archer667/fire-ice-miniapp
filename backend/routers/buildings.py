from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players
from game import (
    now, apply_production, can_afford, pay, normalize_building_state, resolve_building_upgrades,
    owned_castles, castle_building_state,
)
from game_data import BUILDINGS, MAX_BUILDING_LEVEL, building_cost, building_hours, building_produces, building_cap_bonus
from routers.war import all_castle_terrain

router = APIRouter(prefix="/api/buildings", tags=["buildings"])

EMPTY_STATE = {"level": 0, "upgrade_to": None, "ready_at": None}
_resolve = resolve_building_upgrades

def _resolve_castle(p: dict, castle: str | None) -> str:
    """قلعه‌ای که این درخواست برایش است — پیش‌فرض قلعهٔ اصلی؛ اگر castle داده شده
    باید یکی از قلعه‌های همین بازیکن باشد (اصلی یا هرکدام از قلعه‌های اضافه‌اش)"""
    if not castle:
        return p["castle"]
    if castle not in owned_castles(p):
        raise HTTPException(403, "این قلعه مالِ تو نیست")
    return castle

@router.get("")
async def list_buildings(castle: str | None = None, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = _resolve(p)
    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "buildings": p["buildings"], "castle_buildings": p.get("castle_buildings", {}),
    }})

    target_castle = _resolve_castle(p, castle)
    terrain = await all_castle_terrain()
    is_port = terrain.get(target_castle, "land") in ("coastal", "sea")
    state = castle_building_state(p, target_castle)

    out = []
    for bid, meta in BUILDINGS.items():
        st = state.get(bid, EMPTY_STATE)
        level = st["level"]
        target = st["upgrade_to"] or (level + 1 if level < MAX_BUILDING_LEVEL else None)
        per_level_produces = building_produces(bid)
        per_level_cap = building_cap_bonus(bid)
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "unit": meta.get("unit"), "requires_port": meta.get("requires_port", False),
            "level": level, "max_level": MAX_BUILDING_LEVEL,
            "upgrading": bool(st["upgrade_to"]),
            "ready_at": st["ready_at"].isoformat() if st.get("ready_at") else None,
            "next_level": target,
            "next_cost": building_cost(bid, target) if target else None,
            "next_hours": building_hours(bid, target) if target else None,
            # بازدهیِ فعلی (بر اساس لولِ الان) و مقدارِ افزوده به‌ازای هر سطح — خطی‌ست،
            # یعنی هر سطح دقیقاً همین مقدار رو به بازدهیِ قبلی اضافه می‌کنه
            "produces_per_level": per_level_produces,
            "current_yield": {k: v * level for k, v in per_level_produces.items()} if level else {},
            "cap_bonus_per_level": per_level_cap,
            "current_cap_bonus": {k: v * level for k, v in per_level_cap.items()} if level else {},
        })
    return {"castle": target_castle, "is_port": is_port, "castles": owned_castles(p), "buildings": out}

class ActionBody(BaseModel):
    building_id: str
    castle: str | None = None

async def _start_upgrade(building_id: str, castle: str | None, user: dict, require_built: bool):
    if building_id not in BUILDINGS:
        raise HTTPException(400, "ساختمان نامعتبر")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    # اول ارتقاهای تمام‌شده نهایی می‌شن، بعد تولید حساب می‌شه — وگرنه تولیدِ فاصلهٔ
    # زمانیِ سپری‌شده با سطحِ قدیمی (پیش‌از-ارتقا) حساب می‌شه، نه سطحِ واقعیِ الان
    p = _resolve(p)
    p = apply_production(p)

    target_castle = _resolve_castle(p, castle)
    terrain = await all_castle_terrain()
    is_port = terrain.get(target_castle, "land") in ("coastal", "sea")
    state = castle_building_state(p, target_castle)

    st = dict(state.get(building_id, EMPTY_STATE))
    if st["upgrade_to"]:
        raise HTTPException(400, "این ساختمان هم‌اکنون در حال ساخت است")
    if require_built and st["level"] == 0:
        raise HTTPException(400, "اول این ساختمان را بنا کن")
    if not require_built and st["level"] > 0:
        raise HTTPException(400, "این ساختمان قبلاً بنا شده — آن را ارتقا بده")
    if st["level"] >= MAX_BUILDING_LEVEL:
        raise HTTPException(400, "این ساختمان به بیشینهٔ سطح رسیده")
    if not require_built and BUILDINGS[building_id].get("requires_port") and not is_port:
        raise HTTPException(400, "این ساختمان فقط در قلعه/شهرهای دریایی و بندری ساخته می‌شود")

    target = st["level"] + 1
    cost = building_cost(building_id, target)
    hours = building_hours(building_id, target)
    if not can_afford(p["resources"], cost):
        raise HTTPException(400, "منابع کافی نیست")

    pay(p["resources"], cost)
    st["upgrade_to"] = target
    st["ready_at"] = now() + timedelta(hours=hours)
    state[building_id] = st

    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": p["resources"], "buildings": p["buildings"],
        "castle_buildings": p.get("castle_buildings", {}), "last_tick": p["last_tick"],
    }})
    return {"ok": True, "target_level": target, "cost": cost, "ready_at": st["ready_at"].isoformat()}

@router.post("/build")
async def build(body: ActionBody, user: dict = Depends(get_user)):
    return await _start_upgrade(body.building_id, body.castle, user, require_built=False)

@router.post("/upgrade")
async def upgrade(body: ActionBody, user: dict = Depends(get_user)):
    return await _start_upgrade(body.building_id, body.castle, user, require_built=True)
