from datetime import timedelta
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, campaigns, roleplays
from game import now
from game_data import ROLEPLAY_CATEGORIES
from routers.war import ATTACK_OP_TYPES, ROLEPLAY_WINDOW_HOURS

router = APIRouter(prefix="/api/roleplay", tags=["roleplay"])

TEXT_MIN_LEN = 10

class RoleplayBody(BaseModel):
    category: str
    text: str
    campaign_id: str | None = None

@router.post("/send")
async def send(body: RoleplayBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if body.category not in ROLEPLAY_CATEGORIES:
        raise HTTPException(400, "دسته‌بندی نامعتبر است")
    text = body.text.strip()
    if len(text) < TEXT_MIN_LEN:
        raise HTTPException(400, "رول خیلی کوتاه است — کمی بیشتر بنویس")

    campaign_id = None
    if body.category == "war":
        if not body.campaign_id:
            raise HTTPException(400, "برای دستهٔ جنگ باید نبردت را انتخاب کنی")
        try:
            oid = ObjectId(body.campaign_id)
        except Exception:
            raise HTTPException(400, "شناسهٔ نبرد نامعتبر است")
        c = await campaigns.find_one({"_id": oid})
        if not c or c["op_type"] not in ATTACK_OP_TYPES:
            raise HTTPException(404, "این نبرد پیدا نشد")
        is_attacker = c["tg_id"] == user["id"]
        is_defender = c["target_castle"] == p["castle"] and c["tg_id"] != user["id"]
        if not (is_attacker or is_defender):
            raise HTTPException(403, "این نبرد به تو ربطی ندارد")
        arrival_at = c.get("arrival_at")
        if not arrival_at or now() < arrival_at:
            raise HTTPException(400, "این نبرد هنوز به مقصد نرسیده")
        if now() > arrival_at + timedelta(hours=ROLEPLAY_WINDOW_HOURS):
            raise HTTPException(400, f"مهلت {ROLEPLAY_WINDOW_HOURS} ساعته برای فرستادن سناریوی این نبرد گذشته")
        if await roleplays.find_one({"tg_id": user["id"], "campaign_id": body.campaign_id}):
            raise HTTPException(400, "قبلاً سناریوی این نبرد را فرستاده‌ای")
        campaign_id = body.campaign_id

    doc = {
        "tg_id": user["id"], "player_name": p["name"], "castle": p["castle"],
        "category": body.category, "text": text[:4000], "campaign_id": campaign_id,
        "result": None, "resolved": False,
        "created_at": now(),
    }
    res = await roleplays.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    cur = roleplays.find({"tg_id": user["id"]}).sort("created_at", -1).limit(50)
    out = []
    async for r in cur:
        out.append({
            "id": str(r["_id"]), "category": r["category"],
            "category_name": ROLEPLAY_CATEGORIES.get(r["category"], r["category"]),
            "text": r["text"], "resolved": r["resolved"], "result": r["result"],
            "campaign_id": r.get("campaign_id"),
            "created_at": r["created_at"].isoformat(),
        })
    return out
