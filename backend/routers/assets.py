from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from db import players, items, item_grants
from game import now, normalize_building_state, resolve_building_upgrades
from game_data import BUILDINGS, ITEM_TYPES, ITEM_DURATIONS, ITEM_RARITY_COLORS

router = APIRouter(prefix="/api/assets", tags=["assets"])

@router.get("/castle")
async def castle_assets(user: dict = Depends(get_user)):
    """دارایی‌های قلعه — هر ساختمانِ ساخته‌شده و بازدهیِ روزانه/سقفِ فعلی‌اش"""
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = resolve_building_upgrades(p)
    await players.update_one({"tg_id": user["id"]}, {"$set": {"buildings": p["buildings"]}})
    out = []
    for bid, raw in p.get("buildings", {}).items():
        level = normalize_building_state(raw)["level"]
        if level <= 0 or bid not in BUILDINGS:
            continue
        meta = BUILDINGS[bid]
        produces = {k: v * level for k, v in meta.get("produces", {}).items()}
        cap_bonus = {k: v * level for k, v in meta.get("cap_bonus", {}).items()}
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
