from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, messages
from game import now

router = APIRouter(prefix="/api/ravens", tags=["ravens"])

class SendBody(BaseModel):
    to_tg_ids: list[int]
    text: str

@router.post("/send")
async def send(body: SendBody, user: dict = Depends(get_user)):
    me = await players.find_one({"tg_id": user["id"]})
    if not me:
        raise HTTPException(403, "اول ثبت‌نام کن")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "نامه خالی است")
    to_ids = [tid for tid in dict.fromkeys(body.to_tg_ids) if tid != user["id"]]
    if not to_ids:
        raise HTTPException(400, "هیچ گیرنده‌ای انتخاب نشده")

    targets = await players.find({"tg_id": {"$in": to_ids}}).to_list(len(to_ids))
    if not targets:
        raise HTTPException(404, "هیچ‌کدام از گیرنده‌ها پیدا نشدند")

    await messages.insert_many([{
        "from_id": user["id"], "to_id": t["tg_id"],
        "from_name": me["name"], "to_name": t["name"],
        "text": text[:1000], "read": False, "created_at": now(),
    } for t in targets])
    return {"ok": True, "sent_to": len(targets)}

@router.get("/inbox")
async def inbox(user: dict = Depends(get_user)):
    """آخرین نامهٔ هر مکاتبه + شمار خوانده‌نشده"""
    convos = {}
    cur = messages.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}).sort("created_at", -1)
    async for m in cur:
        other = m["to_id"] if m["from_id"] == user["id"] else m["from_id"]
        if other not in convos:
            convos[other] = {
                "with_tg_id": other,
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
