import asyncio
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from db import players
from game import now, add_resources
from config import DAILY_REWARDS
from medals import normalize_stats, sync_medals
from routers.ravens import send_system_message
from control_settings import get as rule

router = APIRouter(prefix="/api/daily", tags=["daily"])

RESOURCE_NAMES = {
    "gold": "طلا", "wood": "چوب", "stone": "سنگ", "iron": "آهن",
    "food": "غله", "wine": "شراب", "men": "نیروی انسانی",
}

def _today_str() -> str:
    return now().strftime("%Y-%m-%d")

def _yesterday_str() -> str:
    return (now() - timedelta(days=1)).strftime("%Y-%m-%d")

def _rewards():
    rewards = rule("daily_rewards.rewards", DAILY_REWARDS)
    return rewards if isinstance(rewards, list) and rewards else DAILY_REWARDS

def _pending_streak(p: dict) -> tuple[int, bool]:
    """استریکی که الان (اگر کلیم کنی) ثبت می‌شود، و اینکه امروز از قبل کلیم شده یا نه"""
    last = p.get("daily_last_claim_date")
    streak = p.get("daily_streak", 0)
    today = _today_str()
    if last == today:
        return streak, True
    missed_limit = max(1, int(rule("daily_rewards.reset_after_missed_days", 1)))
    if last:
        try:
            days = (now().date() - date.fromisoformat(last)).days
        except (ValueError, TypeError):
            days = missed_limit + 1
    else:
        days = missed_limit + 1
    if 1 <= days <= missed_limit:
        return streak + 1, False
    return 1, False

def _day_in_cycle(pending_streak: int) -> int:
    return ((pending_streak - 1) % len(_rewards())) + 1

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
        "cycle_length": len(_rewards()),
        "reward": _rewards()[day_in_cycle - 1],
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
    reward = _rewards()[day_in_cycle - 1]
    res = add_resources(p, reward)

    stats = normalize_stats(p)
    stats["best_daily_streak"] = max(stats.get("best_daily_streak", 0), pending_streak)
    medals = sync_medals(p)
    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": res, "daily_streak": pending_streak, "daily_last_claim_date": _today_str(),
        "stats": stats, "medals": medals,
    }})
    return {"ok": True, "streak": pending_streak, "day_in_cycle": day_in_cycle, "reward": reward, "resources": res}

async def notify_daily_rewards():
    """روزی یک‌بار به بازیکنی که هنوز جایزه را نگرفته خبر می‌دهد.

    فیلد daily_reward_notified_date نقش قفل روزانه را دارد و جلوی اعلان تکراری در چند watcher
    یا بعد از ری‌استارت سرور را می‌گیرد.
    """
    today = _today_str()
    cur = players.find({
        "castle": {"$ne": None},
        "daily_last_claim_date": {"$ne": today},
        "daily_reward_notified_date": {"$ne": today},
    })
    async for p in cur:
        claimed = await players.update_one(
            {
                "_id": p["_id"],
                "daily_last_claim_date": {"$ne": today},
                "daily_reward_notified_date": {"$ne": today},
            },
            {"$set": {"daily_reward_notified_date": today}},
        )
        if not claimed.modified_count:
            continue
        pending_streak, _ = _pending_streak(p)
        day_in_cycle = _day_in_cycle(pending_streak)
        reward = _rewards()[day_in_cycle - 1]
        reward_text = " · ".join(
            f"{amount:,} {RESOURCE_NAMES.get(key, key)}"
            for key, amount in reward.items()
            if amount
        )
        await send_system_message(
            p["tg_id"],
            p["name"],
            f"🎁 جایزهٔ روزانهٔ روز {day_in_cycle} آماده‌ست: {reward_text}\n"
            "برای گرفتنش وارد بازی شو و روی جایزهٔ روزانه بزن.",
            kind="daily",
        )
        # یادآوریِ روزانه ممکنه هم‌زمان برای همه آماده بشه؛ با این فاصله از سقف ارسال تلگرام رد نمی‌شیم.
        await asyncio.sleep(0.05)

