from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from game_data import REGIONS, COMMON_TROOPS, BUILDINGS
from routers import players, war, map as map_router, ravens, leaderboard, admin, construction

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
app.include_router(construction.router)

@app.get("/api/health")
async def health():
    return {"ok": True}

@app.get("/api/gamedata")
async def gamedata():
    """دیتای ثابت برای Frontend — اقلیم‌ها، نیروها، ساختمان‌ها"""
    return {"regions": REGIONS, "troops": COMMON_TROOPS, "buildings": BUILDINGS}
