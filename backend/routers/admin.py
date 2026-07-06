from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin
from db import scenarios, players

router = APIRouter(prefix="/api/admin", tags=["admin"])

async def admin_user(user: dict = Depends(get_user)):
    return await get_admin(user)

@router.get("/pending")
async def pending(user: dict = Depends(admin_user)):
    out = []
    async for s in scenarios.find({"status": "pending"}).sort("created_at", 1):
        out.append({
            "id": str(s["_id"]), "player": s["player_name"],
            "from": s["from_castle"], "to": s["target_castle"],
            "op_type": s["op_type"], "plan": s["plan"],
            "troops": s["troops"], "cost": s["cost"],
            "created_at": s["created_at"].isoformat(),
        })
    return out

class VerdictBody(BaseModel):
    verdict: str
    points_delta: int = 0   # امتیازی که ادمین به بازیکن می‌دهد/می‌گیرد

@router.post("/{scenario_id}/approve")
async def approve(scenario_id: str, body: VerdictBody, user: dict = Depends(admin_user)):
    s = await scenarios.find_one({"_id": ObjectId(scenario_id)})
    if not s:
        raise HTTPException(404, "سناریو پیدا نشد")
    await scenarios.update_one({"_id": s["_id"]},
        {"$set": {"status": "approved", "verdict": body.verdict}})
    if body.points_delta:
        await players.update_one({"tg_id": s["tg_id"]}, {"$inc": {"points": body.points_delta}})
    return {"ok": True}

@router.post("/{scenario_id}/reject")
async def reject(scenario_id: str, body: VerdictBody, user: dict = Depends(admin_user)):
    s = await scenarios.find_one({"_id": ObjectId(scenario_id)})
    if not s:
        raise HTTPException(404, "سناریو پیدا نشد")
    await scenarios.update_one({"_id": s["_id"]},
        {"$set": {"status": "rejected", "verdict": body.verdict}})
    # برگشت طلا هنگام رد
    await players.update_one({"tg_id": s["tg_id"]}, {"$inc": {"resources.gold": s["cost"]}})
    return {"ok": True}
