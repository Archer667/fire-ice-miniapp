from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, messages
from game import now

router = APIRouter(prefix="/api/ravens", tags=["ravens"])

class SendBody(BaseModel):
    to_castle: str
    text: str

@router.post("/send")
async def send(body: SendBody, user: dict = Depends(get_user)):
    me = await players.find_one({"tg_id": user["id"]})
    if not me:
        raise HTTPException(403, "اول ثبت‌نام کن")
    target = await players.find_one({"castle": body.to_castle})
    if not target:
        raise HTTPException(404, "این قلعه لردی ندارد — کلاغ راه گم می‌کند")
    if target["tg_id"] == user["id"]:
        raise HTTPException(400, "برای خودت کلاغ نفرست")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "نامه خالی است")

    await messages.insert_one({
        "from_id": user["id"], "to_id": target["tg_id"],
        "from_name": me["name"], "to_name": target["name"],
        "text": text[:1000], "read": False, "created_at": now(),
    })
    return {"ok": True}

@router.get("/inbox")
async def inbox(user: dict = Depends(get_user)):
    """آخرین نامهٔ هر مکاتبه + شمار خوانده‌نشده"""
    convos = {}
    cur = messages.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}).sort("created_at", -1)
    async for m in cur:
        other = m["to_id"] if m["from_id"] == user["id"] else m["from_id"]
        if other not in convos:
            convos[other] = {
                "with_name": m["to_name"] if m["from_id"] == user["id"] else m["from_name"],
                "last_text": m["text"],
                "last_at": m["created_at"].isoformat(),
                "unread": 0,
            }
        if m["to_id"] == user["id"] and not m["read"]:
            convos[other]["unread"] += 1
    return list(convos.values())

@router.get("/thread/{other_name}")
async def thread(other_name: str, user: dict = Depends(get_user)):
    other = await players.find_one({"name": other_name})
    if not other:
        raise HTTPException(404, "لرد پیدا نشد")
    q = {"$or": [
        {"from_id": user["id"], "to_id": other["tg_id"]},
        {"from_id": other["tg_id"], "to_id": user["id"]},
    ]}
    await messages.update_many({"from_id": other["tg_id"], "to_id": user["id"]}, {"$set": {"read": True}})
    out = []
    async for m in messages.find(q).sort("created_at", 1).limit(100):
        out.append({"mine": m["from_id"] == user["id"], "text": m["text"], "at": m["created_at"].isoformat()})
    return out
