from datetime import timedelta
from fastapi import APIRouter, Depends
from auth import get_user
from db import campaigns, map_castles
from game import now
from game_data import REGIONS
from config import CAMPAIGN_REVEAL_MINUTES
from ranks import scored_players, get_hierarchy_doc

router = APIRouter(prefix="/api/map", tags=["map"])

@router.get("")
async def get_map(user: dict = Depends(get_user)):
    rows = await scored_players()
    by_tgid = {r["player"]["tg_id"]: r for r in rows}
    h = await get_hierarchy_doc()
    overlord_name = {}
    for rid, tg_id in h.get("overlords", {}).items():
        row = by_tgid.get(tg_id)
        overlord_name[rid] = row["player"]["name"] if row else None

    owners_by_castle = {}
    for r in rows:
        p = r["player"]
        owners_by_castle[p["castle"]] = {
            "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
            "points": r["score"], "overlord_name": overlord_name.get(p["region"]),
        }

    # مختصات و قلعه‌های کاملاً تازه‌ای که ادمین از پنلش به نقشه اضافه کرده
    coords_by_region = {}
    custom_by_region = {}
    async for m in map_castles.find({}):
        coords_by_region.setdefault(m["region"], {})[m["name"]] = [m["x"], m["y"]]
        if m.get("custom"):
            custom_by_region.setdefault(m["region"], []).append({"name": m["name"], "port": m.get("port", False)})

    regions = []
    for rid, r in REGIONS.items():
        castle_list = (
            [{"name": c, "owner": owners_by_castle.get(c), "port": False} for c in r["castles"]] +
            [{"name": c, "owner": owners_by_castle.get(c), "port": True} for c in r["ports"]] +
            [{"name": c["name"], "owner": owners_by_castle.get(c["name"]), "port": c["port"]}
             for c in custom_by_region.get(rid, [])]
        )
        regions.append({
            "id": rid, "name": r["name"],
            "castles": castle_list,
            "coords": coords_by_region.get(rid, {}),
        })

    # لشکرکشی‌های فعال و آشکارشده: ۱۵ دقیقه بعد از فرمان (فرمان خودت را همیشه می‌بینی)
    reveal_before = now() - timedelta(minutes=CAMPAIGN_REVEAL_MINUTES)
    camps = []
    cur = campaigns.find({"active": True}).sort("created_at", -1).limit(50)
    async for s in cur:
        mine = s["tg_id"] == user["id"]
        if mine or s["created_at"] <= reveal_before:
            camps.append({
                "from": s["origin_castle"], "to": s["target_castle"], "op_type": s["op_type"],
                "mine": mine,
                "revealed_minutes_ago": int((now() - s["created_at"]).total_seconds() // 60) - (0 if mine else CAMPAIGN_REVEAL_MINUTES),
            })
    return {"regions": regions, "campaigns": camps}
