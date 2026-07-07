from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players
from game import now, apply_construction, can_afford, pay
from game_data import BUILDINGS

router = APIRouter(prefix="/api/construction", tags=["construction"])

class BuildBody(BaseModel):
    building_id: str

def _state(p: dict) -> dict:
    q = p.get("construction")
    return {
        "buildings": p.get("buildings", {}),
        "queue": None if not q else {
            "building_id": q["building_id"],
            "finishes_at": q["finishes_at"].isoformat(),
        },
        "resources": p["resources"],
    }

@router.get("")
async def get_state(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if apply_construction(p):
        await players.update_one({"tg_id": user["id"]},
            {"$set": {"buildings": p["buildings"], "construction": p["construction"]}})
    return _state(p)

@router.post("/start")
async def start(body: BuildBody, user: dict = Depends(get_user)):
    if body.building_id not in BUILDINGS:
        raise HTTPException(400, "ساختمان نامعتبر")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")

    apply_construction(p)
    if p.get("buildings", {}).get(body.building_id):
        raise HTTPException(409, "این ساختمان قبلاً ساخته شده")
    if p.get("construction"):
        raise HTTPException(409, "یک ساخت‌وساز دیگر در حال انجام است")

    spec = BUILDINGS[body.building_id]
    if not can_afford(p["resources"], spec["cost"]):
        raise HTTPException(400, "منابع کافی نیست")

    pay(p["resources"], spec["cost"])
    p["construction"] = {
        "building_id": body.building_id,
        "finishes_at": now() + timedelta(hours=spec["hours"]),
    }
    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": p["resources"],
        "buildings": p.get("buildings", {}),
        "construction": p["construction"],
    }})
    return _state(p)
