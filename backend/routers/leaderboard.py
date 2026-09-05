from fastapi import APIRouter, Depends
from auth import get_user
from db import admin_roles, players
from medals import medal_rows, normalize_stats
from game_data import REGIONS
from config import ADMIN_IDS, OWNER_ID
from ranks import scored_players, weekly_scored_players, current_week_start

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

RANK_LABEL_FA = {"overlord": "بالادستی", "warden": "والی", "king": "پادشاه/ملکه"}

async def _without_admins(rows: list) -> list:
    """ادمین‌ها (چه از env، چه نقش‌داده‌شده در admin_roles) در لیدربرد نمی‌آیند"""
    admin_ids = set(ADMIN_IDS) | {a["tg_id"] async for a in admin_roles.find({}, {"tg_id": 1})}
    if OWNER_ID is not None:
        admin_ids.add(OWNER_ID)
    return [row for row in rows if row["player"]["tg_id"] not in admin_ids]

async def with_dead_players(rows, weekly=False):
    async for p in players.find({"is_dead": True}):
        snapshot = p.get("death_snapshot", {})
        profile = {**p, "castle": snapshot.get("castle"), "region": snapshot.get("region")}
        score = snapshot.get("score", 0)
        weekly_score = snapshot.get("weekly_score", 0) if snapshot.get("week_start") == current_week_start() else 0
        rows.append({"player": profile, "score": score, "weekly_score": weekly_score, "rank_label": snapshot.get("rank_label")})
    rows.sort(key=lambda row: row["weekly_score" if weekly else "score"], reverse=True)
    return rows

@router.get("")
async def leaderboard(user: dict = Depends(get_user)):
    rows = await _without_admins(await with_dead_players(await scored_players()))
    out = []
    for i, row in enumerate(rows[:50]):
        p = row["player"]
        out.append({
            "is_dead": bool(p.get("is_dead")), "rank": i + 1, "name": p["name"], "title": p.get("title"),
            "profile_image": p.get("profile_image"),
            "castle": p["castle"], "region": REGIONS.get(p.get("region"), {}).get("name", ""),
            "points": row["score"],
            "stats": normalize_stats(p), "medals": medal_rows(p),
            "rank_label": RANK_LABEL_FA.get(row["rank_label"]),
            "me": p["tg_id"] == user["id"],
        })
    return out

@router.get("/weekly")
async def weekly_leaderboard(user: dict = Depends(get_user)):
    """رقابت تازهٔ همین هفته — امتیاز کسب‌شده از دوشنبه تا الان، نه انباشت کل بازی"""
    rows = await _without_admins(await with_dead_players(await weekly_scored_players(), weekly=True))
    out = []
    for i, row in enumerate(rows[:50]):
        p = row["player"]
        out.append({
            "is_dead": bool(p.get("is_dead")), "rank": i + 1, "name": p["name"], "title": p.get("title"),
            "profile_image": p.get("profile_image"),
            "castle": p["castle"], "region": REGIONS.get(p.get("region"), {}).get("name", ""),
            "points": row["weekly_score"],
            "stats": normalize_stats(p), "medals": medal_rows(p),
            "rank_label": RANK_LABEL_FA.get(row["rank_label"]),
            "me": p["tg_id"] == user["id"],
        })
    return out

@router.get("/regions")
async def region_leaderboard(user: dict = Depends(get_user)):
    """اقلیم‌ها بر اساس مجموع امتیاز همهٔ لردهایشان — انگیزهٔ تیمی به‌جای رقابت فردی"""
    rows = await _without_admins(await scored_players())
    totals = {rid: {"total": 0, "count": 0} for rid in REGIONS}
    my_region = None
    for row in rows:
        p = row["player"]
        totals[p["region"]]["total"] += row["score"]
        totals[p["region"]]["count"] += 1
        if p["tg_id"] == user["id"]:
            my_region = p["region"]

    ranked = sorted(REGIONS.keys(), key=lambda rid: totals[rid]["total"], reverse=True)
    out = []
    for i, rid in enumerate(ranked):
        out.append({
            "rank": i + 1, "region": rid, "name": REGIONS[rid]["name"],
            "total_score": totals[rid]["total"], "lord_count": totals[rid]["count"],
            "mine": rid == my_region,
        })
    return out
