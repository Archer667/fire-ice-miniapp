import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from game_data import REGIONS, COMMON_TROOPS, BUILDINGS, MAX_BUILDING_LEVEL, WARDEN_GROUPS, ALLIANCE_TYPES
from db import players, map_castles, admin_roles
from routers import (
    players, war, map as map_router, ravens, leaderboard, admin, espionage,
    buildings as buildings_router, titles as titles_router, diplomacy as diplomacy_router,
    polls as polls_router, trade as trade_router, market as market_router, roleplay as roleplay_router,
)
from routers.war import notify_arrivals
from routers.trade import notify_caravan_arrivals
from routers.market import drift_market_prices

logger = logging.getLogger(__name__)

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
app.include_router(espionage.router)
app.include_router(buildings_router.router)
app.include_router(titles_router.router)
app.include_router(diplomacy_router.router)
app.include_router(polls_router.router)
app.include_router(trade_router.router)
app.include_router(market_router.router)
app.include_router(roleplay_router.router)

async def _arrival_watcher():
    """هر ۳۰ ثانیه لشکرها و کاروان‌هایی که تازه رسیده‌اند را چک می‌کند و کلاغ می‌فرستد"""
    while True:
        try:
            await notify_arrivals()
            await notify_caravan_arrivals()
        except Exception:
            logger.exception("arrival watcher tick failed")
        await asyncio.sleep(30)

async def _market_watcher():
    """هر ۵ دقیقه قیمت‌های بازار وستروس را کمی نوسان می‌دهد"""
    while True:
        try:
            await drift_market_prices()
        except Exception:
            logger.exception("market watcher tick failed")
        await asyncio.sleep(300)

async def _ensure_indexes():
    """ایندکس‌های یکتا برای جلوگیری از رکورد دوتایی زیر بار همزمان (race condition) —
    مثلاً دو ثبت‌نام هم‌زمان با یک قلعه، یا دو بار افزودن یک اسم به نقشه توسط ادمین"""
    try:
        await players.create_index("tg_id", unique=True)
        await players.create_index("castle", unique=True)
        await map_castles.create_index("name", unique=True)
        await admin_roles.create_index("tg_id", unique=True)
    except Exception:
        logger.exception("ensuring unique indexes failed — احتمالاً دادهٔ تکراری از قبل در دیتابیس هست")

@app.on_event("startup")
async def start_background_watchers():
    await _ensure_indexes()
    asyncio.create_task(_arrival_watcher())
    asyncio.create_task(_market_watcher())

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
