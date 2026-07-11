from datetime import timedelta
from fastapi import APIRouter, Depends
from auth import get_user
from db import players, scenarios, map_pins
from game import now
from game_data import REGIONS
from config import CAMPAIGN_REVEAL_MINUTES

router = APIRouter(prefix="/api/map", tags=["map"])

@router.get("")
async def get_map(user: dict = Depends(get_user)):
    # اقلیم‌ها + صاحبان قلعه‌ها
    owners = {}
    async for p in players.find({}, {"castle": 1, "name": 1}):
        owners[p["castle"]] = p["name"]

    pins = {}
    async for pin in map_pins.find({}, {"castle": 1, "x": 1, "y": 1}):
        pins[pin["castle"]] = [pin["x"], pin["y"]]

    def pin_of(c):
        return pins.get(c)

    regions = []
    for rid, r in REGIONS.items():
        regions.append({
            "id": rid, "name": r["name"],
            "castles": [{"name": c, "owner": owners.get(c), "port": False, "pin": pin_of(c)} for c in r["castles"]] +
                       [{"name": c, "owner": owners.get(c), "port": True, "pin": pin_of(c)} for c in r["ports"]],
        })

    # لشکرکشی‌های آشکارشده: ۱۵ دقیقه بعد از فرمان (فرمان خودت را همیشه می‌بینی)
    reveal_before = now() - timedelta(minutes=CAMPAIGN_REVEAL_MINUTES)
    campaigns = []
    cur = scenarios.find({"status": "pending"}).sort("created_at", -1).limit(30)
    async for s in cur:
        mine = s["tg_id"] == user["id"]
        if mine or s["created_at"] <= reveal_before:
            campaigns.append({
                "from": s["from_castle"], "to": s["target_castle"],
                "mine": mine,
                "revealed_minutes_ago": int((now() - s["created_at"]).total_seconds() // 60) - (0 if mine else CAMPAIGN_REVEAL_MINUTES),
            })
    return {"regions": regions, "campaigns": campaigns}
