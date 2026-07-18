from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, roleplays
from game import now
from game_data import ROLEPLAY_CATEGORIES

router = APIRouter(prefix="/api/roleplay", tags=["roleplay"])

TEXT_MIN_LEN = 10

class RoleplayBody(BaseModel):
    category: str
    text: str

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

    doc = {
        "tg_id": user["id"], "player_name": p["name"], "castle": p["castle"],
        "category": body.category, "text": text[:4000],
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
            "created_at": r["created_at"].isoformat(),
        })
    return out
