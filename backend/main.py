import asyncio
import logging
import re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from game import now
from game_data import REGIONS, COMMON_TROOPS, BUILDINGS, MAX_BUILDING_LEVEL, WARDEN_GROUPS, ALLIANCE_TYPES
# نکته: اسم players اینجا عمداً players_col است، نه players (که چند خط پایین‌تر
# ماژول routers.players است) — قبلاً همین‌جا با هم قاطی می‌شدند و _ensure_indexes
# داشت روی ماژول روتر create_index صدا می‌زد (بی‌اثر، ولی چون توی try/except بود
# بی‌سروصدا فقط لاگ می‌شد و هیچ‌وقت هیچ ایندکس یکتایی واقعاً ساخته نمی‌شد)
from db import (
    players as players_col, map_castles, admin_roles, game_settings,
    campaigns, caravans, spy_missions, messages, alliances, roleplays,
)
from routers import (
    players, war, map as map_router, ravens, leaderboard, admin, espionage,
    buildings as buildings_router, titles as titles_router, diplomacy as diplomacy_router,
    polls as polls_router, trade as trade_router, market as market_router, roleplay as roleplay_router,
    assets as assets_router, rumors as rumors_router, daily as daily_router, bot as bot_router,
    tribute as tribute_router,
)
from routers.war import notify_arrivals
from routers.trade import notify_caravan_arrivals
from routers.market import drift_market_prices
from routers.tribute import expire_unpaid_tributes
from routers.titles import pay_monthly_salaries
import telegram_bot

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

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """اگر اینجا نبود، یک خطای برنامه‌نویسیِ مدیریت‌نشده (مثلاً KeyError روی
    دادهٔ قدیمی) به‌جای پاسخ ۵۰۰ معمولی، پاسخی بدون هدرهای CORS برمی‌گرداند —
    چون CORSMiddleware فقط پاسخِ عادیِ خروجی از ExceptionMiddleware را می‌بیند،
    نه پاسخی که این هندلر مستقیماً می‌سازد؛ برای همین هدرهای CORS را اینجا
    خودمان دستی می‌زنیم. بدون این، مرورگر خطای واقعی را نشان نمی‌دهد و فقط
    «Failed to fetch» می‌گوید — یعنی هم برای بازیکن هم برای اشکال‌زدایی ما
    غیرقابل‌ردیابی می‌شود"""
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    headers = {}
    origin = request.headers.get("origin")
    if "*" in CORS_ORIGINS:
        headers["Access-Control-Allow-Origin"] = "*"
    elif origin and (origin in CORS_ORIGINS or (CORS_ORIGIN_REGEX and re.match(CORS_ORIGIN_REGEX, origin))):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500, content={"detail": "خطای غیرمنتظرهٔ سرور — دوباره امتحان کن"}, headers=headers,
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
app.include_router(assets_router.router)
app.include_router(rumors_router.router)
app.include_router(daily_router.router)
app.include_router(bot_router.router)
app.include_router(tribute_router.router)

async def _arrival_watcher():
    """هر ۳۰ ثانیه لشکرها و کاروان‌هایی که تازه رسیده‌اند را چک می‌کند و کلاغ می‌فرستد،
    خراج‌هایی که ۲۴ ساعت مهلت‌شان گذشته و پرداخت نشده را منقضی می‌کند، و حقوقِ ماهانهٔ
    پادشاه/شورای کوچک را (اگر ۳۰ روز گذشته و خزانهٔ رد کیپ کافی بود) واریز می‌کند"""
    while True:
        try:
            await notify_arrivals()
            await notify_caravan_arrivals()
            await expire_unpaid_tributes()
            await pay_monthly_salaries()
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
        await players_col.create_index("tg_id", unique=True)
        # «castle» باید یکتا باشد، اما فقط وقتی واقعاً یک قلعه است — بازیکنِ تازه‌ثبت‌نامی
        # یا بازیکنی که ادمین از خاندانش بیرونش کرده castle=null دارد، و mongo روی ایندکسِ
        # یکتای معمولی، null را هم مثل یک مقدار عادی می‌بیند؛ یعنی به‌محض این‌که *دومین*
        # بازیکنِ بی‌خاندان پیدا می‌شد (ثبت‌نام تازه یا حذف از خاندان)، نوشتن با
        # E11000 duplicate key error رد می‌شد. ایندکسِ قدیمی (غیرِ partial) را پاک
        # می‌کنیم تا بشود همین کلید را این‌بار به‌صورت partial (فقط رشته‌ها) دوباره ساخت
        try:
            await players_col.drop_index("castle_1")
        except Exception:
            pass  # از اول وجود نداشته، یا از قبل partial بوده — بی‌اهمیت
        await players_col.create_index(
            "castle", unique=True, partialFilterExpression={"castle": {"$type": "string"}},
        )
        await map_castles.create_index("name", unique=True)
        await admin_roles.create_index("tg_id", unique=True)
    except Exception:
        logger.exception("ensuring unique indexes failed — احتمالاً دادهٔ تکراری از قبل در دیتابیس هست")

    # ایندکس‌های غیریکتا برای پرس‌وجوهایی که مستقیم روی این فیلدها فیلتر می‌کنند —
    # بدون این‌ها هر واچر (هر ۳۰ ثانیه) و هر لیست پنل ادمین کل کالکشن را اسکن می‌کند،
    # که با انباشته‌شدن تاریخچهٔ لشکرکشی/جاسوسی/پیام با تعداد بازیکن بیشتر کند می‌شود
    try:
        await campaigns.create_index([("active", 1), ("arrival_at", 1)])
        await campaigns.create_index("tg_id")
        await caravans.create_index([("active", 1), ("arrival_at", 1)])
        await caravans.create_index("tg_id")
        await caravans.create_index("target_tg_id")
        await spy_missions.create_index("resolved")
        await spy_missions.create_index("tg_id")
        await messages.create_index("from_id")
        await messages.create_index("to_id")
        await alliances.create_index("from_id")
        await alliances.create_index("to_id")
        await alliances.create_index("status")
        await roleplays.create_index("resolved")
        await roleplays.create_index("tg_id")
    except Exception:
        logger.exception("ensuring secondary indexes failed")

# مختصاتِ ثابتِ شمال — قبلاً فقط سمتِ فرانت (mapCoords.js) بود و هیچ‌وقت واقعاً توی
# map_castles ذخیره نمی‌شد؛ یعنی روی نقشه دیده می‌شدند ولی ادمین راهی برای حذف/ادیتشان
# نداشت چون آن بخش از پنل فقط قلعه‌های ثبت‌شده در دیتابیس را لیست می‌کند. با seed
# کردنشان اینجا (فقط اگر از قبل نبودند — دست‌کاریِ دستیِ ادمین را رونویسی نمی‌کند)
# قلعه‌های شمال هم مثل بقیه، واقعاً قابل‌حذف/ادیت می‌شوند.
NORTH_SEED_COORDS = {
    "وینترفل": (41, 23), "دردفورت": (55, 22.5), "بارولندز": (32, 36),
    "کارهولد": (62, 18), "لاست‌هرت": (58, 8), "تورنز اسکوئر": (35, 26.5),
    "دیپ‌وود موت": (20, 48), "موت کلین": (42, 42), "قلعهٔ سروین": (44, 26),
    "تال‌هارت": (33, 26), "فلینت": (25, 40),
    "وایت هاربر": (48, 39), "بارو‌تاون": (31, 35.5), "بندر دیپ‌وود": (19, 49),
}
NORTH_SEED_PORTS = {"وایت هاربر", "بارو‌تاون", "بندر دیپ‌وود"}

NORTH_SEED_MARKER_ID = "north_map_castles_seeded"

async def _seed_north_map_castles():
    """فقط یک‌بار اجرا می‌شود (نشانه‌اش را در game_settings نگه می‌داریم) — وگرنه اگر
    هر بار استارتاپ دوباره seed می‌کردیم، هر قلعه‌ای که ادمین از نقشه حذف کرده بود با
    ری‌استارت بعدی دوباره زنده می‌شد و اصلاً حذف‌شدنی نمی‌ماند"""
    try:
        if await game_settings.find_one({"_id": NORTH_SEED_MARKER_ID}):
            return
        for name, (x, y) in NORTH_SEED_COORDS.items():
            await map_castles.update_one(
                {"region": "north", "name": name},
                {"$setOnInsert": {
                    "region": "north", "name": name, "x": x, "y": y,
                    "kind": "port" if name in NORTH_SEED_PORTS else "castle",
                    "custom": False, "created_at": now(),
                }},
                upsert=True,
            )
        await game_settings.update_one(
            {"_id": NORTH_SEED_MARKER_ID}, {"$set": {"done_at": now()}}, upsert=True,
        )
    except Exception:
        logger.exception("seeding north map castles failed")

@app.on_event("startup")
async def start_background_watchers():
    await _ensure_indexes()
    await _seed_north_map_castles()
    await telegram_bot.register_webhook()
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
