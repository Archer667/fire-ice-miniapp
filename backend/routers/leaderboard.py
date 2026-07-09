from fastapi import APIRouter, Depends
from auth import get_user
from game_data import REGIONS
from ranks import scored_players

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
