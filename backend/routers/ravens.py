from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, messages, rumors, rumor_views
from game import now
from config import SYSTEM_SENDER_ID, SYSTEM_SENDER_NAME
import telegram_bot
from player_labels import normalize_player_names, titled_name

router = APIRouter(prefix="/api/ravens", tags=["ravens"])

async def send_system_message(
    to_tg_id: int, to_name: str, text: str, kind: str = "general",
    image_url: str | None = None, starts_at=None, ends_at=None,
    via_raven: bool = True, via_bot: bool = True,
    bot_text: str | None = None, bot_parse_mode: str | None = None,
):
    """پیام سیستمی داخل کلاغ و تلگرام؛ ایونت می‌تواند تصویر و بازهٔ زمانی هم داشته باشد."""
    text = await normalize_player_names(text)
    doc = {
        "from_id": SYSTEM_SENDER_ID, "to_id": to_tg_id,
        "from_name": SYSTEM_SENDER_NAME, "to_name": to_name,
        "text": text[:2000], "kind": kind, "read": False, "created_at": now(),
    }
    if image_url:
        doc["image_url"] = image_url[:3_500_000]
    if starts_at:
        doc["starts_at"] = starts_at
    if ends_at:
        doc["ends_at"] = ends_at
    if via_raven:
        await messages.insert_one(doc)
    if via_bot:
        caption = bot_text or f"{SYSTEM_SENDER_NAME}: {text}"
        if image_url: telegram_bot.push_photo(to_tg_id, image_url, caption, parse_mode=bot_parse_mode)
        else: telegram_bot.push(to_tg_id, caption, parse_mode=bot_parse_mode)

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
    for t in targets:
        telegram_bot.push(t["tg_id"], f"نامه‌ای از {titled_name(me)}: {text[:300]}")
    return {"ok": True, "sent_to": len(targets)}

@router.get("/unread")
async def unread(user: dict = Depends(get_user)):
    system_filter = {"to_id": user["id"], "from_id": SYSTEM_SENDER_ID, "read": False}
    personal_filter = {"to_id": user["id"], "from_id": {"$ne": SYSTEM_SENDER_ID}, "read": False}
    announcements = await messages.count_documents(system_filter)
    personal = await messages.count_documents(personal_filter)

    player = await players.find_one({"tg_id": user["id"]}, {"rumors_last_seen_at": 1})
    view = await rumor_views.find_one({"tg_id": user["id"]}, {"seen_at": 1})
    rumor_filter = {"author_tg_id": {"$ne": user["id"]}}
    seen_at = view.get("seen_at") if view else (player or {}).get("rumors_last_seen_at")
    if seen_at:
        rumor_filter["created_at"] = {"$gt": seen_at}
    rumor_count = await rumors.count_documents(rumor_filter)
    latest_rumor = await rumors.find_one(rumor_filter, sort=[("created_at", -1)]) if rumor_count else None

    return {
        "count": announcements + personal + rumor_count,
        "announcements": announcements,
        "messages": personal,
        "rumors": rumor_count,
        "latest_rumor_target": latest_rumor.get("target_name") if latest_rumor else None,
        "latest_rumor_id": str(latest_rumor["_id"]) if latest_rumor else None,
    }

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
                "kind": m.get("kind", "general"),
            }
        if m["to_id"] == user["id"] and not m["read"]:
            convos[other]["unread"] += 1
    return list(convos.values())

@router.get("/thread/{other_tg_id}")
async def thread(other_tg_id: int, user: dict = Depends(get_user)):
    """با شناسهٔ عددی کاربر، نه اسمِ نمایشی — اسم‌ها یکتا نیستند و ممکن است دو بازیکن
    اسمِ یکسان داشته باشند (یا حتی اسمِ رزروشدهٔ «رخدادها» را انتخاب کنند)"""
    if other_tg_id != SYSTEM_SENDER_ID:
        other = await players.find_one({"tg_id": other_tg_id})
        if not other:
            raise HTTPException(404, "لرد پیدا نشد")
    q = {"$or": [
        {"from_id": user["id"], "to_id": other_tg_id},
        {"from_id": other_tg_id, "to_id": user["id"]},
    ]}
    await messages.update_many({"from_id": other_tg_id, "to_id": user["id"]}, {"$set": {"read": True}})
    out = []
    async for m in messages.find(q).sort("created_at", 1).limit(100):
        out.append({
            "mine": m["from_id"] == user["id"], "text": m["text"],
            "kind": m.get("kind", "general"), "at": m["created_at"].isoformat(),
            "image_url": m.get("image_url"),
            "starts_at": m["starts_at"].isoformat() if m.get("starts_at") else None,
            "ends_at": m["ends_at"].isoformat() if m.get("ends_at") else None,
        })
    return out
