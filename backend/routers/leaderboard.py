from fastapi import APIRouter, Depends
from auth import get_user
from game_data import REGIONS
from ranks import scored_players, weekly_scored_players

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

RANK_LABEL_FA = {"overlord": "بالادستی", "warden": "والی", "king": "پادشاه/ملکه"}

@router.get("")
async def leaderboard(user: dict = Depends(get_user)):
    rows = await scored_players()
    out = []
    for i, row in enumerate(rows[:50]):
        p = row["player"]
        out.append({
            "rank": i + 1, "name": p["name"], "title": p.get("title"),
            "castle": p["castle"], "region": REGIONS[p["region"]]["name"],
            "points": row["score"],
            "rank_label": RANK_LABEL_FA.get(row["rank_label"]),
            "me": p["tg_id"] == user["id"],
        })
    return out

@router.get("/weekly")
async def weekly_leaderboard(user: dict = Depends(get_user)):
    """رقابت تازهٔ همین هفته — امتیاز کسب‌شده از دوشنبه تا الان، نه انباشت کل بازی"""
    rows = await weekly_scored_players()
    out = []
    for i, row in enumerate(rows[:50]):
        p = row["player"]
        out.append({
            "rank": i + 1, "name": p["name"], "title": p.get("title"),
            "castle": p["castle"], "region": REGIONS[p["region"]]["name"],
            "points": row["weekly_score"],
            "rank_label": RANK_LABEL_FA.get(row["rank_label"]),
            "me": p["tg_id"] == user["id"],
        })
    return out

@router.get("/regions")
async def region_leaderboard(user: dict = Depends(get_user)):
    """اقلیم‌ها بر اساس مجموع امتیاز همهٔ لردهایشان — انگیزهٔ تیمی به‌جای رقابت فردی"""
    rows = await scored_players()
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
