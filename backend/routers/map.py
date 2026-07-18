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

    # مختصات و نوع آیکنِ هرچه ادمین از پنلش روی نقشه گذاشته (چه اسم موجود چه کاملاً تازه)
    coords_by_region = {}
    kind_by_name = {}
    custom_by_region = {}
    async for m in map_castles.find({}):
        coords_by_region.setdefault(m["region"], {})[m["name"]] = [m["x"], m["y"]]
        kind_by_name[m["name"]] = m.get("kind", "port" if m.get("port") else "castle")
        if m.get("custom"):
            custom_by_region.setdefault(m["region"], []).append({"name": m["name"], "kind": kind_by_name[m["name"]]})

    regions = []
    for rid, r in REGIONS.items():
        def built_in(c, is_port):
            # «port» همیشه از دیتای ثابت بازی می‌آید (برای غارت دریایی و امثالش) — نوع آیکنِ
            # نمایشی را ادمین می‌تواند جدا مشخص کند، بدون اینکه به مکانیزم بازی اثر بگذارد
            return {
                "name": c, "owner": owners_by_castle.get(c), "port": is_port,
                "kind": kind_by_name.get(c, "port" if is_port else "castle"),
            }
        castle_list = (
            [built_in(c, False) for c in r["castles"]] +
            [built_in(c, True) for c in r["ports"]] +
            [{"name": c["name"], "owner": owners_by_castle.get(c["name"]),
              "port": c["kind"] == "port", "kind": c["kind"]}
             for c in custom_by_region.get(rid, [])]
        )
        regions.append({
            "id": rid, "name": r["name"],
            "castles": castle_list,
            "coords": coords_by_region.get(rid, {}),
        })

    # لشکرکشی‌های فعال و آشکارشده: ۳۰ دقیقه بعد از فرمان، زیر نقشه برای همه دیده می‌شوند
    # (فرمان خودت را همیشه می‌بینی)
    reveal_before = now() - timedelta(minutes=CAMPAIGN_REVEAL_MINUTES)
    camps = []
    cur = campaigns.find({"active": True}).sort("created_at", -1).limit(50)
    async for s in cur:
        mine = s["tg_id"] == user["id"]
        if mine or s["created_at"] <= reveal_before:
            arrival_at = s.get("arrival_at")
            camps.append({
                "from": s["origin_castle"], "to": s["target_castle"], "op_type": s["op_type"],
                "name": s.get("name", ""),
                "mine": mine,
                "revealed_minutes_ago": int((now() - s["created_at"]).total_seconds() // 60) - (0 if mine else CAMPAIGN_REVEAL_MINUTES),
                "travel_minutes": s.get("travel_minutes", 0),
                "arrived": (now() >= arrival_at) if arrival_at else True,
            })
    return {"regions": regions, "campaigns": camps}
