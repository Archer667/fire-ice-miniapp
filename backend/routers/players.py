from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players
from game import now, apply_production
from game_data import REGIONS
from config import STARTING_RESOURCES, SEASON_LENGTH_DAYS

router = APIRouter(prefix="/api/players", tags=["players"])

class RegisterBody(BaseModel):
    name: str
    region: str
    castle: str

@router.post("/register")
async def register(body: RegisterBody, user: dict = Depends(get_user)):
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    region = REGIONS[body.region]
    if body.castle not in region["castles"] + region["ports"]:
        raise HTTPException(400, "این قلعه در این اقلیم نیست")

    if await players.find_one({"tg_id": user["id"]}):
        raise HTTPException(409, "قبلاً ثبت‌نام کرده‌ای")
    if await players.find_one({"castle": body.castle}):
        raise HTTPException(409, "این قلعه صاحب دارد — یکی دیگر برگزین")

    doc = {
        "tg_id": user["id"],
        "name": body.name.strip()[:40],
        "region": body.region,
        "castle": body.castle,
        "is_port": body.castle in region["ports"],
        "resources": dict(STARTING_RESOURCES),
        "troops": {},
        "buildings": {},
        "points": 100,
        "created_at": now(),
        "last_tick": now(),
    }
    await players.insert_one(doc)
    return {"ok": True}

@router.get("/me")
async def me(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        return {"registered": False}
    p = apply_production(p)
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"resources": p["resources"], "last_tick": p["last_tick"]}})
    day = min(SEASON_LENGTH_DAYS, ( (now() - p["created_at"]).days % SEASON_LENGTH_DAYS ) + 1)
    rank = 1 + await players.count_documents({"points": {"$gt": p["points"]}})
    total = await players.count_documents({})
    return {
        "registered": True,
        "name": p["name"],
        "region": p["region"],
        "region_name": REGIONS[p["region"]]["name"],
        "castle": p["castle"],
        "is_port": p["is_port"],
        "resources": p["resources"],
        "troops": p.get("troops", {}),
        "points": p["points"],
        "rank": rank, "total_players": total,
        "day": day, "season_length": SEASON_LENGTH_DAYS,
    }
