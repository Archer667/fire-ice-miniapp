from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, rumors
from game import now, apply_production, can_afford, pay
from config import RUMOR_GOLD_COST, RUMOR_POPULARITY_DAMAGE, RUMOR_COOLDOWN_HOURS, POPULARITY_START
from routers.ravens import send_system_message

router = APIRouter(prefix="/api/rumors", tags=["rumors"])

class RumorBody(BaseModel):
    target_tg_id: int
    text: str

@router.post("/send")
async def send_rumor(body: RumorBody, user: dict = Depends(get_user)):
    """کارزار عمومی علیه یک بازیکن — همه می‌بینند، محبوبیت هدف کمی افت می‌کند"""
    if body.target_tg_id == user["id"]:
        raise HTTPException(400, "نمی‌توانی علیه خودت شایعه بسازی")
    text = body.text.strip()
    if len(text) < 10:
        raise HTTPException(400, "متن شایعه خیلی کوتاه است")

    me = await players.find_one({"tg_id": user["id"]})
    if not me:
        raise HTTPException(403, "اول ثبت‌نام کن")
    target = await players.find_one({"tg_id": body.target_tg_id})
    if not target:
        raise HTTPException(404, "این لرد پیدا نشد")

    recent = await rumors.find_one({
        "author_tg_id": user["id"], "target_tg_id": body.target_tg_id,
        "created_at": {"$gt": now() - timedelta(hours=RUMOR_COOLDOWN_HOURS)},
    })
    if recent:
        raise HTTPException(400, f"همین الان علیه این لرد شایعه ساختی — {RUMOR_COOLDOWN_HOURS} ساعت دیگر دوباره امتحان کن")

    me = apply_production(me)
    if not can_afford(me["resources"], {"gold": RUMOR_GOLD_COST}):
        raise HTTPException(400, "طلای کافی برای پخش این شایعه نداری")
    pay(me["resources"], {"gold": RUMOR_GOLD_COST})
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"resources": me["resources"], "last_tick": me["last_tick"]}})

    new_popularity = max(0, target.get("popularity", POPULARITY_START) - RUMOR_POPULARITY_DAMAGE)
    await players.update_one({"tg_id": target["tg_id"]}, {"$set": {"popularity": new_popularity}})

    doc = {
        "author_tg_id": user["id"], "author_name": me["name"],
        "target_tg_id": target["tg_id"], "target_name": target["name"],
        "text": text[:400], "created_at": now(),
    }
    res = await rumors.insert_one(doc)

    await send_system_message(
        target["tg_id"], target["name"],
        "شایعه‌ای علیه‌ات در وستروس پیچیده و محبوبیتت کمی افت کرد — از تب «شایعات» ببینش.",
    )
    return {"ok": True, "id": str(res.inserted_id)}

@router.get("")
async def list_rumors(user: dict = Depends(get_user)):
    """فید عمومی شایعات — همهٔ بازیکنان همه‌چیز را می‌بینند"""
    out = []
    cur = rumors.find({}).sort("created_at", -1).limit(50)
    async for r in cur:
        out.append({
            "id": str(r["_id"]), "author": r["author_name"], "author_tg_id": r["author_tg_id"],
            "target": r["target_name"], "target_tg_id": r["target_tg_id"],
            "text": r["text"], "created_at": r["created_at"].isoformat(),
            "mine": r["author_tg_id"] == user["id"],
        })
    return out
