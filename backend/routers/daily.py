from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from db import players
from game import now, effective_caps
from config import DAILY_REWARDS

router = APIRouter(prefix="/api/daily", tags=["daily"])

def _today_str() -> str:
    return now().strftime("%Y-%m-%d")

def _yesterday_str() -> str:
    return (now() - timedelta(days=1)).strftime("%Y-%m-%d")

def _pending_streak(p: dict) -> tuple[int, bool]:
    """استریکی که الان (اگر کلیم کنی) ثبت می‌شود، و اینکه امروز از قبل کلیم شده یا نه"""
    last = p.get("daily_last_claim_date")
    streak = p.get("daily_streak", 0)
    today = _today_str()
    if last == today:
        return streak, True
    if last == _yesterday_str():
        return streak + 1, False
    return 1, False

def _day_in_cycle(pending_streak: int) -> int:
    return ((pending_streak - 1) % len(DAILY_REWARDS)) + 1

@router.get("/status")
async def daily_status(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    pending_streak, claimed_today = _pending_streak(p)
    day_in_cycle = _day_in_cycle(pending_streak)
    return {
        "current_streak": p.get("daily_streak", 0),
        "claimed_today": claimed_today,
        "day_in_cycle": day_in_cycle,
        "cycle_length": len(DAILY_REWARDS),
        "reward": DAILY_REWARDS[day_in_cycle - 1],
    }

@router.post("/claim")
async def daily_claim(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    pending_streak, claimed_today = _pending_streak(p)
    if claimed_today:
        raise HTTPException(400, "امروز جایزه‌ات را گرفته‌ای — فردا دوباره سر بزن")

    day_in_cycle = _day_in_cycle(pending_streak)
    reward = DAILY_REWARDS[day_in_cycle - 1]
    caps = effective_caps(p)
    res = p["resources"]
    for k, v in reward.items():
        res[k] = min(caps.get(k, 10 ** 9), res.get(k, 0) + v)

    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": res, "daily_streak": pending_streak, "daily_last_claim_date": _today_str(),
    }})
    return {"ok": True, "streak": pending_streak, "day_in_cycle": day_in_cycle, "reward": reward, "resources": res}
