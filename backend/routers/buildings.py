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
from routers.ravens import send_system_message

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
        max_level = int(meta.get("max_level", MAX_BUILDING_LEVEL))
        target = st["upgrade_to"] or (level + 1 if level < max_level else None)
        per_level_produces = building_produces(bid)
        per_level_cap = building_cap_bonus(bid)
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "unit": meta.get("unit"), "requires_port": meta.get("requires_port", False),
            "level": level, "max_level": max_level,
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
    max_level = int(BUILDINGS[building_id].get("max_level", MAX_BUILDING_LEVEL))
    if st["level"] >= max_level:
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

async def notify_building_completions():
    """ساختمان‌های آماده را حتی وقتی بازیکن داخل اپ نیست نهایی و یک‌بار اطلاع‌رسانی می‌کند.

    هر ساختمان با یک آپدیت شرطی claim می‌شود تا اگر چند worker هم‌زمان watcher را اجرا کردند،
    پیام تکراری برای بازیکن نرود.
    """
    cur = players.find(
        {"castle": {"$ne": None}},
        {"tg_id": 1, "name": 1, "castle": 1, "buildings": 1, "castle_buildings": 1},
    )
    async for p in cur:
        completed = []
        scopes = [(p.get("castle"), "buildings", p.get("buildings", {}))]
        for castle, state in p.get("castle_buildings", {}).items():
            scopes.append((castle, f"castle_buildings.{castle}", state))

        for castle, prefix, state in scopes:
            if not castle:
                continue
            for bid, raw in list(state.items()):
                st = normalize_building_state(raw)
                ready = st.get("ready_at")
                target = st.get("upgrade_to")
                if isinstance(ready, str):
                    ready = datetime.fromisoformat(ready)
                if not target or not ready or ready > now():
                    continue

                field = f"{prefix}.{bid}"
                raw_ready = raw.get("ready_at") if isinstance(raw, dict) else ready
                claimed = await players.update_one(
                    {
                        "_id": p["_id"],
                        f"{field}.upgrade_to": target,
                        f"{field}.ready_at": raw_ready,
                    },
                    {"$set": {
                        f"{field}.level": target,
                        f"{field}.upgrade_to": None,
                        f"{field}.ready_at": None,
                    }},
                )
                if claimed.modified_count:
                    building_name = BUILDINGS.get(bid, {}).get("name", bid)
                    completed.append(f"🏗️ {building_name} در {castle} به سطح {target} رسید")

        if completed:
            await send_system_message(
                p["tg_id"],
                p["name"],
                "ساخت‌وساز تمام شد:\n" + "\n".join(completed) + "\nبرای دیدن اثرش وارد صفحهٔ ساختمان‌ها شو.",
                kind="building",
            )

