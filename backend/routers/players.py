import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players
from game import now, apply_production
from game_data import REGIONS
from config import STARTING_RESOURCES, SEASON_LENGTH_DAYS, POPULARITY_START, TAX_RATE_DEFAULT, DEFAULT_TITLE, max_tax_rate
from ranks import scored_players

router = APIRouter(prefix="/api/players", tags=["players"])

class RegisterBody(BaseModel):
    name: str
    region: str
    castle: str
    gender: str   # "lord" | "lady"

@router.post("/register")
async def register(body: RegisterBody, user: dict = Depends(get_user)):
    if body.region not in REGIONS:
        raise HTTPException(400, "اقلیم نامعتبر")
    region = REGIONS[body.region]
    if body.castle not in region["castles"] + region["ports"]:
        raise HTTPException(400, "این قلعه در این اقلیم نیست")
    if body.gender not in DEFAULT_TITLE:
        raise HTTPException(400, "جنسیت نامعتبر")

    if await players.find_one({"tg_id": user["id"]}):
        raise HTTPException(409, "قبلاً ثبت‌نام کرده‌ای")
    if await players.find_one({"castle": body.castle}):
        raise HTTPException(409, "این قلعه صاحب دارد — یکی دیگر برگزین")

    doc = {
        "tg_id": user["id"],
        "name": body.name.strip()[:40],
        "gender": body.gender,
        "title": DEFAULT_TITLE[body.gender],
        "region": body.region,
        "castle": body.castle,
        "is_port": body.castle in region["ports"],
        "resources": dict(STARTING_RESOURCES),
        "troops": {},
        "buildings": {},
        "points": 100,
        "popularity": POPULARITY_START,
        "tax_rate": TAX_RATE_DEFAULT,
        "alliance_count": 0,
        "last_feast": None,
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

    rows = await scored_players()
    total = len(rows)
    rank = 1
    score = 0
    rank_label = None
    for i, row in enumerate(rows):
        if row["player"]["tg_id"] == user["id"]:
            rank = i + 1
            score = row["score"]
            rank_label = row["rank_label"]
            break

    popularity = p.get("popularity", POPULARITY_START)
    return {
        "registered": True,
        "name": p["name"],
        "gender": p.get("gender", "lord"),
        "title": p.get("title", DEFAULT_TITLE.get(p.get("gender", "lord"))),
        "rank_label": rank_label,
        "region": p["region"],
        "region_name": REGIONS[p["region"]]["name"],
        "castle": p["castle"],
        "is_port": p["is_port"],
        "resources": p["resources"],
        "troops": p.get("troops", {}),
        "points": score,
        "alliance_count": p.get("alliance_count", 0),
        "popularity": popularity,
        "tax_rate": p.get("tax_rate", TAX_RATE_DEFAULT),
        "max_tax_rate": max_tax_rate(popularity),
        "rank": rank, "total_players": total,
        "day": day, "season_length": SEASON_LENGTH_DAYS,
    }

@router.get("/search")
async def search(q: str = "", user: dict = Depends(get_user)):
    """جست‌وجوی لردها بر اساس نام یا قلعه — برای انتخاب گیرندهٔ کلاغ/پیمان"""
    q = q.strip()
    if len(q) < 2:
        return []
    pattern = re.escape(q)
    cur = players.find(
        {"tg_id": {"$ne": user["id"]}, "$or": [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"castle": {"$regex": pattern, "$options": "i"}},
        ]},
        {"tg_id": 1, "name": 1, "castle": 1, "region": 1, "title": 1},
    ).limit(20)
    return [{
        "tg_id": p["tg_id"], "name": p["name"], "castle": p["castle"],
        "region_name": REGIONS.get(p["region"], {}).get("name", p["region"]),
        "title": p.get("title"),
    } async for p in cur]

class TaxBody(BaseModel):
    rate: int

@router.post("/tax")
async def set_tax(body: TaxBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)
    cap = max_tax_rate(p.get("popularity", POPULARITY_START))
    if not (0 <= body.rate <= cap):
        raise HTTPException(400, f"نرخ مالیات باید بین ۰ تا {cap} درصد باشد")
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"tax_rate": body.rate, "resources": p["resources"], "last_tick": p["last_tick"]}})
    return {"ok": True, "tax_rate": body.rate}
