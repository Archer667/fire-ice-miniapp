from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admin_notifications import notify_admins
from auth import get_full_admin, get_user
from db import players, support_tickets
from routers.ravens import send_system_message

router = APIRouter(prefix="/api/support", tags=["support"])

CATEGORIES = {"roleplay": "رول", "battle": "سناریو نبرد", "technical": "مشکل فنی"}
STATUSES = {"open": "تازه", "in_review": "در حال بررسی", "answered": "پاسخ داده شده", "closed": "بسته شده"}


async def full_admin(user=Depends(get_user)):
    return await get_full_admin(user)


class CreateTicket(BaseModel):
    category: str
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10, max_length=5000)


class PlayerReply(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class AdminAction(BaseModel):
    text: str = Field(default="", max_length=5000)
    status: str = "answered"


def _oid(value: str):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "تیکت پیدا نشد")
    return ObjectId(value)


def _message(row):
    at = row.get("at")
    return {
        "author": row.get("author", "player"),
        "name": row.get("name", ""),
        "text": row.get("text", ""),
        "at": at.isoformat() if at else None,
    }


def _ticket(row, admin=False):
    result = {
        "id": str(row["_id"]), "category": row["category"],
        "category_label": CATEGORIES[row["category"]], "title": row["title"],
        "status": row["status"], "status_label": STATUSES[row["status"]],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "messages": [_message(item) for item in row.get("messages", [])],
    }
    if admin:
        result["player"] = {"tg_id": row["tg_id"], "name": row.get("player_name", "بازیکن")}
    return result


@router.get("/meta")
async def meta(user=Depends(get_user)):
    return {"categories": [{"id": key, "label": value} for key, value in CATEGORIES.items()],
            "statuses": [{"id": key, "label": value} for key, value in STATUSES.items()]}


@router.post("")
async def create_ticket(body: CreateTicket, user=Depends(get_user)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "موضوع تیکت معتبر نیست")
    player = await players.find_one({"tg_id": user["id"]}, {"name": 1})
    player_name = (player or {}).get("name") or user.get("first_name") or "بازیکن"
    stamp = datetime.now(timezone.utc)
    doc = {
        "tg_id": user["id"], "player_name": player_name, "category": body.category,
        "title": body.title.strip(), "status": "open", "created_at": stamp, "updated_at": stamp,
        "messages": [{"author": "player", "name": player_name, "text": body.description.strip(), "at": stamp}],
    }
    result = await support_tickets.insert_one(doc)
    ticket_id = str(result.inserted_id)
    await notify_admins(
        "support_ticket", "🎫 تیکت جدید", f"{player_name} · {CATEGORIES[body.category]}\n{doc['title']}",
        dedupe_key=f"support-ticket:{ticket_id}", player_name=player_name,
        player_tg_id=user["id"], source_id=ticket_id,
        action="پنل ادمین ← داوری و ارتباط ← تیکت‌ها", audience_roles=("owner", "full"),
    )
    doc["_id"] = result.inserted_id
    return _ticket(doc)


@router.get("/mine")
async def mine(user=Depends(get_user)):
    rows = await support_tickets.find({"tg_id": user["id"]}).sort("updated_at", -1).limit(100).to_list(100)
    return [_ticket(row) for row in rows]


@router.post("/{ticket_id}/reply")
async def player_reply(ticket_id: str, body: PlayerReply, user=Depends(get_user)):
    oid = _oid(ticket_id)
    row = await support_tickets.find_one({"_id": oid, "tg_id": user["id"]})
    if not row:
        raise HTTPException(404, "تیکت پیدا نشد")
    if row["status"] == "closed":
        raise HTTPException(409, "این تیکت بسته شده است")
    stamp = datetime.now(timezone.utc)
    await support_tickets.update_one({"_id": oid}, {"$push": {"messages": {
        "author": "player", "name": row.get("player_name", "بازیکن"), "text": body.text.strip(), "at": stamp,
    }}, "$set": {"status": "open", "updated_at": stamp}})
    await notify_admins(
        "support_ticket", "🎫 پاسخ تازه در تیکت", f"{row.get('player_name', 'بازیکن')} · {row['title']}",
        dedupe_key=f"support-reply:{ticket_id}:{stamp.isoformat()}", player_name=row.get("player_name"),
        player_tg_id=user["id"], source_id=ticket_id, action="تیکت را بررسی کن.",
        audience_roles=("owner", "full"),
    )
    return {"ok": True}


@router.get("/admin/list")
async def admin_list(status: str = Query(default=""), category: str = Query(default=""),
                     q: str = Query(default="", max_length=100), admin=Depends(full_admin)):
    query = {}
    if status:
        if status not in STATUSES: raise HTTPException(400, "وضعیت معتبر نیست")
        query["status"] = status
    if category:
        if category not in CATEGORIES: raise HTTPException(400, "موضوع معتبر نیست")
        query["category"] = category
    if q.strip():
        import re
        needle = re.escape(q.strip())
        query["$or"] = [{"title": {"$regex": needle, "$options": "i"}},
                        {"player_name": {"$regex": needle, "$options": "i"}}]
    rows = await support_tickets.find(query).sort("updated_at", -1).limit(300).to_list(300)
    return [_ticket(row, True) for row in rows]


@router.post("/admin/{ticket_id}")
async def admin_action(ticket_id: str, body: AdminAction, admin=Depends(full_admin)):
    if body.status not in STATUSES:
        raise HTTPException(400, "وضعیت معتبر نیست")
    oid = _oid(ticket_id)
    row = await support_tickets.find_one({"_id": oid})
    if not row:
        raise HTTPException(404, "تیکت پیدا نشد")
    text = body.text.strip()
    if body.status == "answered" and not text:
        raise HTTPException(400, "متن پاسخ را بنویس")
    stamp = datetime.now(timezone.utc)
    update = {"$set": {"status": body.status, "updated_at": stamp,
                       "handled_by": admin["id"], "handled_at": stamp}}
    if text:
        update["$push"] = {"messages": {"author": "admin", "name": "پشتیبانی والریا", "text": text, "at": stamp}}
    await support_tickets.update_one({"_id": oid}, update)
    if text:
        await send_system_message(row["tg_id"], row.get("player_name", ""),
                                  f"🎫 تیکت «{row['title']}» پاسخ داده شد.\n{text}", kind="support")
    return {"ok": True, "status": body.status, "status_label": STATUSES[body.status]}
