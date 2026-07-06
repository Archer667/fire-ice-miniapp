from fastapi import APIRouter, Depends
from auth import get_user
from db import players
from game_data import REGIONS

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

@router.get("")
async def leaderboard(user: dict = Depends(get_user)):
    out = []
    rank = 0
    async for p in players.find({}).sort("points", -1).limit(50):
        rank += 1
        out.append({
            "rank": rank, "name": p["name"],
            "castle": p["castle"], "region": REGIONS[p["region"]]["name"],
            "points": p["points"], "me": p["tg_id"] == user["id"],
        })
    return out
