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
    to_tg_ids: list[int]
    type: str
    name: str = ""

@router.post("/propose")
async def propose(body: ProposeBody, user: dict = Depends(get_user)):
    if body.type not in ALLIANCE_TYPES:
        raise HTTPException(400, "نوع پیمان نامعتبر")
    me = await players.find_one({"tg_id": user["id"]})
    if not me:
        raise HTTPException(403, "اول ثبت‌نام کن")

    target_ids = [tid for tid in dict.fromkeys(body.to_tg_ids) if tid != user["id"]]
    if not target_ids:
        raise HTTPException(400, "هیچ گیرنده‌ای انتخاب نشده")
    targets = await players.find({"tg_id": {"$in": target_ids}}).to_list(len(target_ids))
    if not targets:
        raise HTTPException(404, "هیچ‌کدام از گیرنده‌های انتخابی پیدا نشدند")

    # حذف کسانی که همین الان پیمانی از همین نوع باهاشون در جریان است
    valid_targets = []
    for t in targets:
        existing = await alliances.find_one({
            "type": body.type, "status": {"$in": ["pending", "accepted"]},
            "$or": [
                {"from_id": user["id"], "to_id": t["tg_id"]},
                {"from_id": t["tg_id"], "to_id": user["id"]},
            ],
        })
        if not existing:
            valid_targets.append(t)
    if not valid_targets:
        raise HTTPException(409, "با همهٔ گیرنده‌های انتخابی، پیمانی از همین نوع از قبل داری")

    me = apply_production(me)
    unit_cost = ALLIANCE_TYPES[body.type]["wine_cost"]
    total_cost = {"wine": unit_cost * len(valid_targets)}
    if not can_afford(me["resources"], total_cost):
        raise HTTPException(400, f"شراب کافی برای پیشنهاد به {len(valid_targets)} نفر نداری")
    pay(me["resources"], total_cost)
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"resources": me["resources"], "last_tick": me["last_tick"]}})

    pact_name = body.name.strip()[:60]
    await alliances.insert_many([{
        "from_id": user["id"], "from_name": me["name"],
        "to_id": t["tg_id"], "to_name": t["name"],
        "type": body.type, "wine_cost": unit_cost, "name": pact_name,
        "status": "pending", "created_at": now(),
    } for t in valid_targets])
    return {"ok": True, "sent_to": len(valid_targets), "skipped": len(targets) - len(valid_targets)}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    out = []
    cur = alliances.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}).sort("created_at", -1)
    async for a in cur:
        mine_proposed = a["from_id"] == user["id"]
        out.append({
            "id": str(a["_id"]),
            "mine_proposed": mine_proposed,
            "other_id": a["to_id"] if mine_proposed else a["from_id"],
            "other_name": a["to_name"] if mine_proposed else a["from_name"],
            "type": a["type"], "type_name": ALLIANCE_TYPES[a["type"]]["name"],
            "name": a.get("name", ""),
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
