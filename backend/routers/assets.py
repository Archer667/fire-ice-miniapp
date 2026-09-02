from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from db import players, items, item_grants
from game import now, apply_production, normalize_building_state, owned_castles, castle_building_state, production_fields
from game_data import BUILDINGS, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS, building_produces, building_cap_bonus, CASTLE_HOUSES
from routers.war import all_castle_terrain

router = APIRouter(prefix="/api/assets", tags=["assets"])

@router.get("/castles")
async def my_castles(user: dict = Depends(get_user)):
    """همهٔ قلعه‌های این بازیکن — اصلی + هرچی به‌عنوانِ غنیمتِ جنگ یا تصمیمِ ادمین گرفته"""
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    terrain = await all_castle_terrain()
    return [
        {"name": c, "home": c == p["castle"], "house": CASTLE_HOUSES.get(c),
         "is_port": terrain.get(c, "land") in ("coastal", "sea")}
        for c in owned_castles(p)
    ]

@router.get("/castle")
async def castle_assets(castle: str | None = None, user: dict = Depends(get_user)):
    """دارایی‌های یک قلعهٔ مشخص — هر ساختمانِ ساخته‌شده و بازدهیِ روزانه/سقفِ فعلی‌اش"""
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)
    await players.update_one({"tg_id": user["id"]}, {"$set": production_fields(p)})
    target_castle = castle or p["castle"]
    if target_castle not in owned_castles(p):
        raise HTTPException(403, "این قلعه مالِ تو نیست")
    state = castle_building_state(p, target_castle)
    out = []
    for bid, raw in state.items():
        level = normalize_building_state(raw)["level"]
        if level <= 0 or bid not in BUILDINGS:
            continue
        meta = BUILDINGS[bid]
        produces = {k: v * level for k, v in building_produces(bid).items()}
        cap_bonus = {k: v * level for k, v in building_cap_bonus(bid).items()}
        out.append({
            "id": bid, "name": meta["name"], "type": meta.get("type", "economy"),
            "level": level, "produces": produces, "cap_bonus": cap_bonus,
        })
    out.sort(key=lambda r: (-r["level"], r["name"]))
    return out

@router.get("/items")
async def my_items(user: dict = Depends(get_user)):
    """آیتم‌های لرد — دارایی‌های شخصی که ادمین به او داده؛ آیتم موقتیِ منقضی‌شده دیگر نشان داده نمی‌شود"""
    out = []
    cur = item_grants.find({"tg_id": user["id"]}).sort("granted_at", -1)
    async for g in cur:
        expires_at = g.get("expires_at")
        if expires_at and now() >= expires_at:
            continue
        tpl = await items.find_one({"_id": g["item_id"]})
        if not tpl:
            continue
        out.append({
            "id": str(g["_id"]), "item_id": str(tpl["_id"]),
            "name": tpl["name"], "type": tpl["type"], "type_name": ITEM_TYPES.get(tpl["type"], tpl["type"]),
            "description": tpl.get("description", ""),
            "duration": tpl["duration"], "duration_name": ITEM_DURATIONS.get(tpl["duration"], tpl["duration"]),
            "color": g["color"], "color_name": ITEM_RARITY_COLORS.get(g["color"], g["color"]),
            "granted_at": g["granted_at"].isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
        })
    return out
