from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from game_data import REGIONS, COMMON_TROOPS, BUILDINGS, MAX_BUILDING_LEVEL, WARDEN_GROUPS, ALLIANCE_TYPES
from routers import (
    players, war, map as map_router, ravens, leaderboard, admin,
    buildings as buildings_router, titles as titles_router, diplomacy as diplomacy_router,
)

app = FastAPI(title="نغمه آتش و یخ — API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(war.router)
app.include_router(map_router.router)
app.include_router(ravens.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)
app.include_router(buildings_router.router)
app.include_router(titles_router.router)
app.include_router(diplomacy_router.router)

@app.get("/api/health")
async def health():
    return {"ok": True}

@app.get("/api/gamedata")
async def gamedata():
    """دیتای ثابت برای Frontend — اقلیم‌ها، نیروها، ساختمان‌ها، والی‌نشین‌ها، پیمان‌ها"""
    return {
        "regions": REGIONS, "troops": COMMON_TROOPS, "buildings": BUILDINGS,
        "max_building_level": MAX_BUILDING_LEVEL, "warden_groups": WARDEN_GROUPS,
        "alliance_types": ALLIANCE_TYPES,
    }
