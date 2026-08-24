import asyncio
import logging
import re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import CORS_ORIGINS, CORS_ORIGIN_REGEX
from game import now
import game_data
from game_data import REGIONS, COMMON_TROOPS, BUILDINGS, MAX_BUILDING_LEVEL, WARDEN_GROUPS, ALLIANCE_TYPES
# نکته: اسم players اینجا عمداً players_col است، نه players (که چند خط پایین‌تر
# ماژول routers.players است) — قبلاً همین‌جا با هم قاطی می‌شدند و _ensure_indexes
# داشت روی ماژول روتر create_index صدا می‌زد (بی‌اثر، ولی چون توی try/except بود
# بی‌سروصدا فقط لاگ می‌شد و هیچ‌وقت هیچ ایندکس یکتایی واقعاً ساخته نمی‌شد)
from db import (
    players as players_col, map_castles, admin_roles, game_settings,
    campaigns, ambushes, caravans, spy_missions, messages, alliances, roleplays, tributes,
    rebellion_checks, rebellions, admin_notifications,
)
from routers import (
    players, war, map as map_router, ravens, leaderboard, admin, espionage,
    buildings as buildings_router, titles as titles_router, diplomacy as diplomacy_router,
    polls as polls_router, trade as trade_router, market as market_router, roleplay as roleplay_router,
    assets as assets_router, rumors as rumors_router, daily as daily_router, bot as bot_router,
    tribute as tribute_router, rebellions as rebellions_router,
)
from routers.war import notify_arrivals
from routers.trade import notify_caravan_arrivals
from routers.market import drift_market_prices
from routers.tribute import expire_unpaid_tributes
from routers.titles import pay_daily_salaries
from routers.rebellions import evaluate_rebellions
from routers.buildings import notify_building_completions
from routers.daily import notify_daily_rewards
from admin_notifications import notify_admin_deadlines
import telegram_bot

logger = logging.getLogger(__name__)

# API deployment marker: battle-centered roleplay/admin endpoints are available.
app = FastAPI(title="والریا : سیزن اول — API", version="1.0")

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
app.include_router(rebellions_router.router)

async def _arrival_watcher():
    """هر ۳۰ ثانیه رسیدن لشکر و کاروان، پایان ساخت و آماده‌شدن جایزهٔ روزانه را چک می‌کند،
    خراج‌هایی که ۲۴ ساعت مهلت‌شان گذشته و پرداخت نشده را منقضی می‌کند، و حقوقِ روزانهٔ
    پادشاه/شورای کوچک را (اگر یک روز گذشته و خزانهٔ رد کیپ کافی بود) واریز می‌کند"""
    while True:
        try:
            await notify_arrivals()
            await notify_caravan_arrivals()
            await notify_building_completions()
            await notify_daily_rewards()
            await notify_admin_deadlines()
            await expire_unpaid_tributes()
            await pay_daily_salaries()
            await evaluate_rebellions()
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
        # فقط یه خراجِ پرداخت‌نشده هم‌زمان بینِ همون دو نفر مجازه — بدونِ این ایندکس،
        # دو درخواستِ هم‌زمانِ /tribute/demand می‌تونستن هردو از چکِ pending رد بشن
        await tributes.create_index(
            [("from_id", 1), ("to_id", 1)], unique=True,
            partialFilterExpression={"status": "pending"},
        )
    except Exception:
        logger.exception("ensuring unique indexes failed — احتمالاً دادهٔ تکراری از قبل در دیتابیس هست")

    # ایندکس‌های غیریکتا برای پرس‌وجوهایی که مستقیم روی این فیلدها فیلتر می‌کنند —
    # بدون این‌ها هر واچر (هر ۳۰ ثانیه) و هر لیست پنل ادمین کل کالکشن را اسکن می‌کند،
    # که با انباشته‌شدن تاریخچهٔ لشکرکشی/جاسوسی/پیام با تعداد بازیکن بیشتر کند می‌شود
    try:
        await campaigns.create_index([("active", 1), ("arrival_at", 1)])
        await campaigns.create_index("tg_id")
        await ambushes.create_index([("edge_key", 1), ("status", 1)])
        await ambushes.create_index("tg_id")
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
        await admin_notifications.create_index("dedupe_key", unique=True)
        await admin_notifications.create_index([("created_at", -1)])
        await roleplays.create_index("resolved")
        await roleplays.create_index("tg_id")
        await roleplays.create_index([("category", 1), ("created_at", -1)])
        await rebellion_checks.create_index([("tg_id", 1), ("day", 1)], unique=True)
        await rebellions.create_index([("status", 1), ("deadline", 1)])
        await rebellions.create_index("tg_id")
    except Exception:
        logger.exception("ensuring secondary indexes failed")

BUILDING_OVERRIDES_DOC_ID = "building_overrides"

async def _load_building_overrides():
    """مقادیرِ بازدهی/سقفِ سراسری‌ای که ادمین از تب «تعادل بازی» بازنویسی کرده رو موقع
    استارتاپ تو حافظه می‌ریزه — بدونش، بعد از هر ری‌استارتِ سرور بازنویسی‌های ادمین
    به مقادیرِ پیش‌فرضِ کدِ BUILDINGS برمی‌گشت"""
    try:
        doc = await game_settings.find_one({"_id": BUILDING_OVERRIDES_DOC_ID})
        game_data.BUILDING_OVERRIDES.clear()
        for bid, override in (doc or {}).get("overrides", {}).items():
            meta = game_data.BUILDINGS.get(bid)
            if not meta:
                continue
            clean = dict(override)
            for field in ("produces", "cap_bonus"):
                if field in clean:
                    allowed = set(meta.get(field, {}))
                    clean[field] = {k: v for k, v in clean[field].items() if k in allowed}
                    if not clean[field]:
                        clean.pop(field)
            game_data.BUILDING_OVERRIDES[bid] = clean
    except Exception:
        logger.exception("loading building overrides failed")

CASTLE_ROSTER_V2_MARKER_ID = "castle_roster_v2_migrated"

async def _migrate_castle_roster_v2():
    """فقط یک‌بار اجرا می‌شود — با جایگزین‌شدنِ کامل نقشه (REGIONS/CASTLE_HOUSES/
    CASTLE_TRAVEL_EDGES با قلعه‌های جدید)، پین‌های قدیمیِ map_castles دیگر معنی
    ندارند و پاک می‌شوند. چیزی از players پاک نمی‌شود — فقط بازیکن‌هایی که به
    قلعه‌ای تخصیص دارند که در نقشهٔ جدید نیست، در لاگ گزارش می‌شوند تا از پنل
    ادمین دوباره برایشان قلعهٔ جدید تعیین شود."""
    try:
        if await game_settings.find_one({"_id": CASTLE_ROSTER_V2_MARKER_ID}):
            return
        new_names = set()
        for region in REGIONS.values():
            new_names |= set(region["castles"]) | set(region["ports"])

        deleted = await map_castles.delete_many({})
        logger.info("castle_roster_v2: پاک شد %d پینِ قلعهٔ قدیمی از map_castles", deleted.deleted_count)

        orphaned = []
        async for p in players_col.find({"castle": {"$exists": True, "$ne": None}}, {"tg_id": 1, "name": 1, "castle": 1}):
            if p.get("castle") and p["castle"] not in new_names:
                orphaned.append(p)
        if orphaned:
            logger.warning(
                "castle_roster_v2: %d بازیکن به قلعه‌ای تخصیص دارند که در نقشهٔ جدید نیست — از پنل ادمین دوباره تخصیص بده: %s",
                len(orphaned),
                ", ".join(f"{p.get('name')}(tg_id={p['tg_id']}):{p['castle']}" for p in orphaned),
            )
        else:
            logger.info("castle_roster_v2: هیچ بازیکنی به قلعهٔ حذف‌شده تخصیص نداشت")

        await game_settings.update_one(
            {"_id": CASTLE_ROSTER_V2_MARKER_ID}, {"$set": {"done_at": now(), "orphaned_count": len(orphaned)}}, upsert=True,
        )
    except Exception:
        logger.exception("castle roster v2 migration failed")

@app.on_event("startup")
async def start_background_watchers():
    await _ensure_indexes()
    await _migrate_castle_roster_v2()
    await _load_building_overrides()
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

