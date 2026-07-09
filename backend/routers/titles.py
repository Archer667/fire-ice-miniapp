from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin
from db import players, hierarchy
from game_data import WARDEN_GROUPS
from ranks import region_overlords, get_hierarchy_doc, group_of_region, wardens_of, HIERARCHY_ID

router = APIRouter(prefix="/api/titles", tags=["titles"])

def _brief(p):
    if not p:
        return None
    return {"tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"), "castle": p["castle"]}

@router.get("")
async def get_titles(user: dict = Depends(get_user)):
    overlords = await region_overlords()
    h = await get_hierarchy_doc()

    warden_holders = {}
    for gid in WARDEN_GROUPS:
        tg_id = h.get(f"warden_{gid}")
        holder = await players.find_one({"tg_id": tg_id}) if tg_id else None
        warden_holders[gid] = _brief(holder)

    king_holder = await players.find_one({"tg_id": h.get("king")}) if h.get("king") else None

    return {
        "overlords": {rid: _brief(p) for rid, p in overlords.items()},
        "warden_groups": WARDEN_GROUPS,
        "wardens": warden_holders,
        "king": _brief(king_holder),
    }

async def admin_user(user: dict = Depends(get_user)):
    return await get_admin(user)

class WardenBody(BaseModel):
    group: str        # "south" | "central" | "north"
    tg_id: int

@router.post("/warden")
async def set_warden(body: WardenBody, user: dict = Depends(admin_user)):
    if body.group not in WARDEN_GROUPS:
        raise HTTPException(400, "والی‌نشین نامعتبر")
    target = await players.find_one({"tg_id": body.tg_id})
    if not target:
        raise HTTPException(404, "بازیکن پیدا نشد")

    overlords = await region_overlords()
    is_overlord_of_group = any(
        o and o["tg_id"] == body.tg_id and group_of_region(rid) == body.group
        for rid, o in overlords.items()
    )
    if not is_overlord_of_group:
        raise HTTPException(400, "این بازیکن الان بالادستیِ هیچ‌کدام از اقلیم‌های این والی‌نشین نیست")

    await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$set": {f"warden_{body.group}": body.tg_id}}, upsert=True)
    return {"ok": True}

class KingBody(BaseModel):
    tg_id: int

@router.post("/king")
async def set_king(body: KingBody, user: dict = Depends(admin_user)):
    h = await get_hierarchy_doc()
    if body.tg_id not in wardens_of(h):
        raise HTTPException(400, "پادشاه/ملکه فقط از بین والی‌های فعلی انتخاب می‌شود")
    await hierarchy.update_one({"_id": HIERARCHY_ID}, {"$set": {"king": body.tg_id}}, upsert=True)
    return {"ok": True}

class EpithetBody(BaseModel):
    tg_id: int
    title: str

@router.post("/epithet")
async def set_epithet(body: EpithetBody, user: dict = Depends(admin_user)):
    title = body.title.strip()[:60]
    if not title:
        raise HTTPException(400, "عنوان خالی است")
    res = await players.update_one({"tg_id": body.tg_id}, {"$set": {"title": title}})
    if res.matched_count == 0:
        raise HTTPException(404, "بازیکن پیدا نشد")
    return {"ok": True, "title": title}
