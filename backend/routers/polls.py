from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_full_admin
from db import polls, players
from game import now

router = APIRouter(prefix="/api/polls", tags=["polls"])

def _tally(poll: dict) -> list:
    counts = [0] * len(poll["options"])
    for opt in poll.get("votes", {}).values():
        if 0 <= opt < len(counts):
            counts[opt] += 1
    return counts

def _brief(poll: dict, user_id: int) -> dict:
    votes = poll.get("votes", {})
    return {
        "id": str(poll["_id"]),
        "question": poll["question"],
        "options": poll["options"],
        "status": poll["status"],
        "tally": _tally(poll),
        "total_votes": len(votes),
        "eligible": user_id in poll.get("eligible", []),
        "my_vote": votes.get(str(user_id)),
        "created_at": poll["created_at"].isoformat(),
    }

@router.get("")
async def list_polls(user: dict = Depends(get_user)):
    """همهٔ رای‌گیری‌ها (باز و بسته) — نتیجه برای همه قابل‌دیدنه، فقط واجدشرایط‌ها می‌توانند رای بدهند"""
    out = []
    async for p in polls.find({}).sort("created_at", -1).limit(30):
        out.append(_brief(p, user["id"]))
    return out

class VoteBody(BaseModel):
    option: int

@router.post("/{poll_id}/vote")
async def vote(poll_id: str, body: VoteBody, user: dict = Depends(get_user)):
    p = await polls.find_one({"_id": ObjectId(poll_id)})
    if not p:
        raise HTTPException(404, "رای‌گیری پیدا نشد")
    if p["status"] != "open":
        raise HTTPException(400, "این رای‌گیری بسته شده")
    if user["id"] not in p.get("eligible", []):
        raise HTTPException(403, "تو در این رای‌گیری واجد شرایط نیستی")
    if not (0 <= body.option < len(p["options"])):
        raise HTTPException(400, "گزینهٔ نامعتبر")

    await polls.update_one({"_id": p["_id"]}, {"$set": {f"votes.{user['id']}": body.option}})
    p = await polls.find_one({"_id": p["_id"]})
    return _brief(p, user["id"])

async def admin_user(user: dict = Depends(get_user)):
    """ساخت/بستن رای‌گیری فقط با ادمین کامل"""
    return await get_full_admin(user)

class CreatePollBody(BaseModel):
    question: str
    options: list[str]
    eligible_tg_ids: list[int]

@router.post("/admin/create")
async def create_poll(body: CreatePollBody, user: dict = Depends(admin_user)):
    question = body.question.strip()
    options = [o.strip() for o in body.options if o.strip()]
    if not question:
        raise HTTPException(400, "سوال خالی است")
    if len(options) < 2:
        raise HTTPException(400, "حداقل دو گزینه لازم است")
    if not body.eligible_tg_ids:
        raise HTTPException(400, "حداقل یک واجد شرایط لازم است")

    doc = {
        "question": question[:300], "options": options,
        "eligible": body.eligible_tg_ids, "status": "open",
        "votes": {}, "created_at": now(), "created_by": user["id"],
    }
    res = await polls.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id)}

@router.post("/admin/{poll_id}/close")
async def close_poll(poll_id: str, user: dict = Depends(admin_user)):
    res = await polls.update_one({"_id": ObjectId(poll_id)}, {"$set": {"status": "closed"}})
    if res.matched_count == 0:
        raise HTTPException(404, "رای‌گیری پیدا نشد")
    return {"ok": True}

@router.delete("/admin/{poll_id}")
async def delete_poll(poll_id: str, user: dict = Depends(admin_user)):
    """حذف کامل یک رای‌گیری — چه باز چه بسته"""
    res = await polls.delete_one({"_id": ObjectId(poll_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "رای‌گیری پیدا نشد")
    return {"ok": True}
