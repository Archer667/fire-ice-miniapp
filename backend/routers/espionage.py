from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, spy_missions
from game import now, can_afford, pay
from game_data import spy_travel_minutes
from config import SPY_GOLD_COST, SPY_MEN_COST

router = APIRouter(prefix="/api/espionage", tags=["espionage"])

SCENARIO_MIN_LEN = 10

class SpyBody(BaseModel):
    target_castle: str
    scenario: str

@router.post("/send")
async def send(body: SpyBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")

    scenario = body.scenario.strip()
    if len(scenario) < SCENARIO_MIN_LEN:
        raise HTTPException(400, "سناریوی جاسوسی خیلی کوتاه است — نقشه‌ات را کمی بیشتر توضیح بده")

    target = await players.find_one({"castle": body.target_castle})
    if not target:
        raise HTTPException(404, "این قلعه صاحبی ندارد که جاسوسی‌اش کنی")
    if target["tg_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی جاسوس به قلعهٔ خودت بفرستی")

    if not can_afford(p["resources"], {"gold": SPY_GOLD_COST}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < SPY_MEN_COST:
        raise HTTPException(400, "نفرات کافی نداری")

    pay(p["resources"], {"gold": SPY_GOLD_COST})
    p["resources"]["men"] -= SPY_MEN_COST
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    travel = spy_travel_minutes(p["castle"], target["castle"])
    arrival_at = now() + timedelta(minutes=travel)

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": p["castle"], "target_castle": body.target_castle, "target_tg_id": target["tg_id"],
        "scenario": scenario,
        "gold_cost": SPY_GOLD_COST, "men_sent": SPY_MEN_COST,
        "travel_minutes": travel, "arrival_at": arrival_at,
        "admin_score": None, "resolved": False, "success": None, "report": None,
        "created_at": now(),
    }
    res = await spy_missions.insert_one(doc)
    return {"ok": True, "id": str(res.inserted_id), "travel_minutes": travel}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    """با .get() و مقدار پیش‌فرض می‌خوانیم، نه اندیس مستقیم — یک رکورد قدیمی‌تر
    (از نسخه‌ای از کد که هنوز فلان فیلد را نداشت) نباید کل این endpoint را با
    KeyError بترکاند و به فرانت به‌شکل «Failed to fetch» برسد"""
    cur = spy_missions.find({"tg_id": user["id"]}).sort("created_at", -1).limit(30)
    out = []
    async for m in cur:
        resolved = m.get("resolved", False)
        success = m.get("success") if resolved else None
        created_at = m.get("created_at") or now()
        out.append({
            "id": str(m["_id"]), "target": m.get("target_castle", ""),
            "scenario": m.get("scenario", ""),
            "travel_minutes": m.get("travel_minutes", 0), "arrived": now() >= m.get("arrival_at", now()),
            "resolved": resolved,
            "success": success,
            "report": m.get("report") if resolved and success else None,
            "created_at": created_at.isoformat(),
        })
    return out
