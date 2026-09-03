from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, spy_missions
from game import now, can_afford, pay
from game_data import spy_travel_minutes
from config import SPY_GOLD_COST, SPY_MEN_COST
from routers.war import owner_of_castle
from admin_notifications import notify_admins
from control_settings import get as rule, feature_enabled

router = APIRouter(prefix="/api/espionage", tags=["espionage"])

SCENARIO_MIN_LEN = 10

class SpyBody(BaseModel):
    target_castle: str
    scenario: str

@router.post("/send")
async def send(body: SpyBody, user: dict = Depends(get_user)):
    if not feature_enabled("espionage"):
        raise HTTPException(503, "جاسوسی فعلاً غیرفعال است")
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")

    scenario = body.scenario.strip()
    if len(scenario) < SCENARIO_MIN_LEN:
        raise HTTPException(400, "سناریوی جاسوسی خیلی کوتاه است — نقشه‌ات را کمی بیشتر توضیح بده")

    target = await owner_of_castle(body.target_castle)
    if not target:
        raise HTTPException(404, "این قلعه صاحبی ندارد که جاسوسی‌اش کنی")
    if target["tg_id"] == user["id"]:
        raise HTTPException(400, "نمی‌توانی جاسوس به قلعهٔ خودت بفرستی")

    gold_cost = int(rule("war.spy_gold_cost", SPY_GOLD_COST)); men_cost = int(rule("war.spy_men_cost", SPY_MEN_COST))
    if not can_afford(p["resources"], {"gold": gold_cost}):
        raise HTTPException(400, "خزانه کافی نیست")
    if p["resources"].get("men", 0) < men_cost:
        raise HTTPException(400, "نفرات کافی نداری")

    pay(p["resources"], {"gold": gold_cost})
    p["resources"]["men"] -= men_cost
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    travel = spy_travel_minutes(p["castle"], body.target_castle)
    arrival_at = now() + timedelta(minutes=travel)

    doc = {
        "tg_id": user["id"], "player_name": p["name"],
        "origin_castle": p["castle"], "target_castle": body.target_castle, "target_tg_id": target["tg_id"],
        "scenario": scenario[:4000],
        "gold_cost": gold_cost, "men_sent": men_cost,
        "travel_minutes": travel, "arrival_at": arrival_at,
        "admin_score": None, "resolved": False, "success": None, "report": None,
        "created_at": now(),
    }
    res = await spy_missions.insert_one(doc)
    await notify_admins(
        "espionage",
        "👁️ سناریوی جاسوسی تازه",
        f"{p['name']} از {p['castle']} برای جاسوسی از {body.target_castle} سناریو فرستاد.",
        dedupe_key=f"spy-submitted:{res.inserted_id}",
        priority="normal",
        player_name=p["name"],
        player_tg_id=user["id"],
        castle=body.target_castle,
        action="از پنل ادمین ← جنگ و رول‌ها ← جاسوسی، سناریو را امتیاز بده.",
        source_id=str(res.inserted_id),
        deadline=arrival_at,
    )
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
