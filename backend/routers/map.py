from datetime import timedelta
from fastapi import APIRouter, Depends
from auth import get_user
from db import campaigns, map_castles, alliances
from game import now
from game_data import REGIONS, CASTLE_HOUSES
from game import owned_castles
from config import CAMPAIGN_REVEAL_MINUTES
from ranks import scored_players, get_hierarchy_doc
from routers.war import all_castle_terrain

router = APIRouter(prefix="/api/map", tags=["map"])

# اولویتِ نمایش وقتی با یک نفر چند پیمان هم‌زمان برقرار است — قوی‌ترین رابطه رنگ پین را تعیین می‌کند
PACT_PRIORITY = ["full_alliance", "non_aggression", "trade"]

@router.get("")
async def get_map(user: dict = Depends(get_user)):
    rows = await scored_players()
    by_tgid = {r["player"]["tg_id"]: r for r in rows}
    h = await get_hierarchy_doc()
    overlord_name = {}
    for rid, tg_id in h.get("overlords", {}).items():
        row = by_tgid.get(tg_id)
        overlord_name[rid] = row["player"]["name"] if row else None

    # پیمان‌های برقرار من با بقیه — برای رنگ‌بندی پین‌ها بر اساس پیمان روی نقشه
    pact_by_tgid = {}
    cur = alliances.find({"status": "accepted", "$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]})
    async for a in cur:
        other_id = a["to_id"] if a["from_id"] == user["id"] else a["from_id"]
        prev = pact_by_tgid.get(other_id)
        if prev is None or PACT_PRIORITY.index(a["type"]) < PACT_PRIORITY.index(prev):
            pact_by_tgid[other_id] = a["type"]

    # اقلیمِ واقعیِ هر قلعه — از رویِ خودِ پینِ نقشه‌اش (نه اقلیمِ خانگیِ صاحبش)؛ قلعه‌های
    # استاتیکِ بدون پینِ اختصاصی هم از دیتای ثابت پیش‌فرض می‌گیرن. لازمه چون یه لرد
    # می‌تونه قلعهٔ دومی در اقلیمِ دیگه‌ای داشته باشه — بالادستیِ اون پین باید بالادستیِ
    # همون اقلیم باشه، نه اقلیمِ خانگیِ لرد
    castle_region = {}
    for rid, r in REGIONS.items():
        for c in r["castles"] + r["ports"]:
            castle_region[c] = rid

    # مختصات و نوع آیکنِ هرچه ادمین از پنلش روی نقشه گذاشته (چه اسم موجود چه کاملاً تازه)
    coords_by_region = {}
    kind_by_name = {}
    custom_by_region = {}
    async for m in map_castles.find({}):
        coords_by_region.setdefault(m["region"], {})[m["name"]] = [m["x"], m["y"]]
        kind_by_name[m["name"]] = m.get("kind", "port" if m.get("port") else "castle")
        castle_region[m["name"]] = m["region"]
        if m.get("custom"):
            custom_by_region.setdefault(m["region"], []).append({"name": m["name"], "kind": kind_by_name[m["name"]]})

    owners_by_castle = {}
    for r in rows:
        p = r["player"]
        for c in owned_castles(p):
            rid = castle_region.get(c, p["region"])
            owners_by_castle[c] = {
                "tg_id": p["tg_id"], "name": p["name"], "title": p.get("title"),
                "points": r["score"], "overlord_name": overlord_name.get(rid),
                "region": rid, "pact": pact_by_tgid.get(p["tg_id"]),
            }

    # terrain: land | coastal | sea — همان چیزی که ادمین از تب نقشه روی هر پین مشخص کرده
    # (یا پیش‌فرضِ استاتیک برای قلعه‌هایی که هنوز پین نگرفته‌اند)؛ «port» از همین مشتق می‌شود
    terrain_by_name = await all_castle_terrain()

    regions = []
    for rid, r in REGIONS.items():
        def built_in(c):
            terrain = terrain_by_name.get(c, "land")
            return {
                "name": c, "owner": owners_by_castle.get(c), "port": terrain in ("coastal", "sea"),
                "kind": kind_by_name.get(c, "port" if terrain in ("coastal", "sea") else "castle"),
                "house": CASTLE_HOUSES.get(c), "terrain": terrain,
            }
        castle_list = (
            [built_in(c) for c in r["castles"] + r["ports"]] +
            [{"name": c["name"], "owner": owners_by_castle.get(c["name"]),
              "port": terrain_by_name.get(c["name"], "land") in ("coastal", "sea"), "kind": c["kind"],
              "house": CASTLE_HOUSES.get(c["name"]), "terrain": terrain_by_name.get(c["name"], "land")}
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
    # فقط ارتش‌های واقعاً در راه؛ قبلاً لشکرهای دفاعی/مستقرِ رسیده هم سقف ۵۰تایی
    # این Query را پر می‌کردند و ممکن بود یک حرکت واقعی اصلاً به فرانت نرسد.
    cur = campaigns.find({"active": True, "arrival_at": {"$gt": now()}}).sort("arrival_at", 1).limit(100)
    async for s in cur:
        mine = s["tg_id"] == user["id"]
        departed_at = s.get("moved_at") or s.get("created_at")
        if mine or departed_at <= reveal_before:
            arrival_at = s.get("arrival_at")
            owner_row = by_tgid.get(s["tg_id"])
            owner = owner_row["player"] if owner_row else None
            camps.append({
                "id": str(s["_id"]),
                "from": s["origin_castle"], "to": s["target_castle"],
                "op_type": s["op_type"] if mine else None,
                "name": s.get("name", "") if mine else "لشکر در حرکت",
                "mine": mine,
                "player_name": s.get("player_name", ""),
                "owner_region": owner.get("region") if owner else None,
                "route_path": s.get("route_path") or [s["origin_castle"], s["target_castle"]],
                "departed_at": departed_at.isoformat() if departed_at else None,
                "arrival_at": arrival_at.isoformat() if arrival_at else None,
                "revealed_minutes_ago": int((now() - departed_at).total_seconds() // 60) - (0 if mine else CAMPAIGN_REVEAL_MINUTES),
                "travel_minutes": s.get("travel_minutes", 0),
                "arrived": (now() >= arrival_at) if arrival_at else True,
            })
    return {"regions": regions, "campaigns": camps}
