from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from db import players, scenarios
from game import now, can_afford, pay
from game_data import COMMON_TROOPS, REGIONS, SPECIAL_TROOP_COST

router = APIRouter(prefix="/api/war", tags=["war"])

class ScenarioBody(BaseModel):
    op_type: str            # حمله / محاصره / ...
    target_castle: str
    plan: str
    troops: dict            # {troop_id: count}

def troop_cost(region: str, troops: dict) -> int:
    total = 0
    specials = REGIONS[region]["special"]
    for tid, n in troops.items():
        if n <= 0: continue
        if tid in COMMON_TROOPS:
            total += COMMON_TROOPS[tid]["cost"] * n
        elif tid in specials:
            total += SPECIAL_TROOP_COST * n
        else:
            raise HTTPException(400, f"نیروی نامعتبر: {tid}")
    return total

@router.post("/submit")
async def submit(body: ScenarioBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    if len(body.plan) < 50:
        raise HTTPException(400, "سناریو خیلی کوتاه است — نقشه‌ات را شرح بده")

    cost = troop_cost(p["region"], body.troops)
    if cost <= 0:
        raise HTTPException(400, "هیچ نیرویی گسیل نکرده‌ای")
    if not can_afford(p["resources"], {"gold": cost}):
        raise HTTPException(400, "خزانه کافی نیست")

    pay(p["resources"], {"gold": cost})
    await players.update_one({"tg_id": user["id"]}, {"$set": {"resources": p["resources"]}})

    await scenarios.insert_one({
        "tg_id": user["id"], "player_name": p["name"],
        "from_castle": p["castle"],
        "op_type": body.op_type, "target_castle": body.target_castle,
        "plan": body.plan, "troops": body.troops, "cost": cost,
        "status": "pending",          # pending | approved | rejected
        "verdict": "",
        "created_at": now(),
    })
    return {"ok": True, "cost": cost}

@router.get("/mine")
async def mine(user: dict = Depends(get_user)):
    cur = scenarios.find({"tg_id": user["id"]}).sort("created_at", -1).limit(20)
    out = []
    async for s in cur:
        out.append({
            "op_type": s["op_type"], "target": s["target_castle"],
            "status": s["status"], "verdict": s.get("verdict", ""),
            "cost": s["cost"], "created_at": s["created_at"].isoformat(),
        })
    return out
