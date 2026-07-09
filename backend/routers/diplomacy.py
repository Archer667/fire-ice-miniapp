from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, alliances
from game import now, apply_production, can_afford, pay
from game_data import ALLIANCE_TYPES
from config import FEAST_COST, FEAST_POPULARITY_GAIN, FEAST_COOLDOWN_HOURS, POPULARITY_MAX

router = APIRouter(prefix="/api/diplomacy", tags=["diplomacy"])

class ProposeBody(BaseModel):
    to_castle: str
    type: str

@router.post("/propose")
async def propose(body: ProposeBody, user: dict = Depends(get_user)):
    if body.type not in ALLIANCE_TYPES:
        raise HTTPException(400, "نوع پیمان نامعتبر")
    me = await players.find_one({"tg_id": user["id"]})
    if not me:
        raise HTTPException(403, "اول ثبت‌نام کن")
    target = await players.find_one({"castle": body.to_castle})
    if not target:
        raise HTTPException(404, "این قلعه لردی ندارد")
    if target["tg_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی با خودت پیمان ببندی")

    existing = await alliances.find_one({
        "type": body.type, "status": {"$in": ["pending", "accepted"]},
        "$or": [
            {"from_id": user["id"], "to_id": target["tg_id"]},
            {"from_id": target["tg_id"], "to_id": user["id"]},
        ],
    })
    if existing:
        raise HTTPException(409, "پیمانی از همین نوع بین شما از قبل هست")

    me = apply_production(me)
    cost = {"wine": ALLIANCE_TYPES[body.type]["wine_cost"]}
    if not can_afford(me["resources"], cost):
        raise HTTPException(400, "شراب کافی برای این پیمان نداری")
    pay(me["resources"], cost)
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"resources": me["resources"], "last_tick": me["last_tick"]}})

    await alliances.insert_one({
        "from_id": user["id"], "from_name": me["name"],
        "to_id": target["tg_id"], "to_name": target["name"],
        "type": body.type, "wine_cost": cost["wine"],
        "status": "pending", "created_at": now(),
    })
    return {"ok": True}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    out = []
    cur = alliances.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}).sort("created_at", -1)
    async for a in cur:
        out.append({
            "id": str(a["_id"]),
            "mine_proposed": a["from_id"] == user["id"],
            "other_name": a["to_name"] if a["from_id"] == user["id"] else a["from_name"],
            "type": a["type"], "type_name": ALLIANCE_TYPES[a["type"]]["name"],
            "status": a["status"],
        })
    return out

class RespondBody(BaseModel):
    accept: bool

@router.post("/{alliance_id}/respond")
async def respond(alliance_id: str, body: RespondBody, user: dict = Depends(get_user)):
    a = await alliances.find_one({"_id": ObjectId(alliance_id)})
    if not a:
        raise HTTPException(404, "پیمان پیدا نشد")
    if a["to_id"] != user["id"]:
        raise HTTPException(403, "این پیمان برای تو نیست")
    if a["status"] != "pending":
        raise HTTPException(400, "این پیمان قبلاً پاسخ داده شده")

    if body.accept:
        await alliances.update_one({"_id": a["_id"]}, {"$set": {"status": "accepted"}})
        await players.update_one({"tg_id": a["from_id"]}, {"$inc": {"alliance_count": 1}})
        await players.update_one({"tg_id": a["to_id"]}, {"$inc": {"alliance_count": 1}})
    else:
        await alliances.update_one({"_id": a["_id"]}, {"$set": {"status": "rejected"}})
        await players.update_one({"tg_id": a["from_id"]}, {"$inc": {"resources.wine": a["wine_cost"]}})
    return {"ok": True}

@router.post("/feast")
async def feast(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)

    last_feast = p.get("last_feast")
    if last_feast:
        if isinstance(last_feast, str):
            last_feast = datetime.fromisoformat(last_feast)
        if now() - last_feast < timedelta(hours=FEAST_COOLDOWN_HOURS):
            raise HTTPException(400, "ضیافت را همین امروز برگزار کرده‌ای — فردا دوباره امتحان کن")

    if not can_afford(p["resources"], FEAST_COST):
        raise HTTPException(400, "شراب یا غذای کافی برای ضیافت نداری")
    pay(p["resources"], FEAST_COST)
    popularity = min(POPULARITY_MAX, p.get("popularity", 0) + FEAST_POPULARITY_GAIN)

    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": p["resources"], "last_tick": p["last_tick"],
        "popularity": popularity, "last_feast": now(),
    }})
    return {"ok": True, "popularity": popularity}
