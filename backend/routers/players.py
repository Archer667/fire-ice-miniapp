import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin_role
from db import players, campaigns, alliances, game_settings
from game import now, apply_production, effective_caps, owned_castles, production_fields
from medals import medal_rows, normalize_stats, sync_medals
from admin_notifications import notify_admins
from game_data import REGIONS, CASTLE_HOUSES
from config import STARTING_RESOURCES, SEASON_LENGTH_DAYS, POPULARITY_START, TAX_RATE_DEFAULT, DEFAULT_TITLE
from ranks import scored_players
from routers.war import apply_campaign_upkeep, all_castle_names_and_ports
from registration import castle_region_map, registration_state
from control_settings import get as rule, feature_enabled

router = APIRouter(prefix="/api/players", tags=["players"])

MUSIC_SETTINGS_ID = "background_music"

@router.get("/music")
async def background_music(user: dict = Depends(get_user)):
    """تنظیم عمومی موسیقی؛ پخش واقعی با رضایت مرورگر/بازیکن در فرانت انجام می‌شود."""
    doc = await game_settings.find_one({"_id": MUSIC_SETTINGS_ID}) or {}
    return {
        "enabled": bool(doc.get("enabled", False)),
        "title": doc.get("title", "موسیقی والریا"),
        "audio_url": doc.get("audio_url", ""),
        "volume": max(0, min(100, int(doc.get("volume", 35)))),
        "loop": bool(doc.get("loop", True)),
        "autoplay": bool(doc.get("autoplay", True)),
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }

MAX_REQUESTED_CASTLES = 5

class RegisterBody(BaseModel):
    name: str
    gender: str   # "lord" | "lady"
    requested_castles: list[str] = []   # اولویتِ خودِ بازیکن — چون ممکنه اولی‌ها قبلاً اشغال شده باشن
    backstory: str
    profile_image: str | None = None

@router.post("/register")
async def register(body: RegisterBody, user: dict = Depends(get_user)):
    """فقط نام، جنسیت، و لیستِ اولویتیِ خاندان‌های درخواستی — خودِ تخصیصِ نهاییِ
    اقلیم/قلعه رو ادمین بعداً از پنلش دستی انجام می‌ده"""
    if not feature_enabled("registration"):
        raise HTTPException(503, "ثبت‌نام فعلاً توسط ادمین اصلی بسته شده است")
    if body.gender not in DEFAULT_TITLE:
        raise HTTPException(400, "جنسیت نامعتبر")
    if not body.name.strip():
        raise HTTPException(400, "نام نمی‌تواند خالی باشد")
    if len(body.backstory.strip()) < 40 or len(body.backstory.strip()) > 2000:
        raise HTTPException(400, "بک‌استوری باید بین ۴۰ تا ۲۰۰۰ نویسه باشد")
    if body.profile_image:
        if not body.profile_image.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
            raise HTTPException(400, "عکس پروفایل باید JPG، PNG یا WebP باشد")
        if len(body.profile_image) > 3_500_000:
            raise HTTPException(400, "حجم عکس پروفایل باید حداکثر ۲٫۵ مگابایت باشد")
    existing = await players.find_one({"tg_id": user["id"]})
    if existing and not existing.get("registration_reset"):
        raise HTTPException(409, "قبلاً ثبت‌نام کرده‌ای")

    requested = list(dict.fromkeys(c.strip() for c in body.requested_castles if c.strip()))[:MAX_REQUESTED_CASTLES]
    if not requested:
        raise HTTPException(400, "انتخاب دست‌کم یک قلعه الزامی است")
    names, _ports = await all_castle_names_and_ports()
    bad = [c for c in requested if c not in names]
    if bad:
        raise HTTPException(400, f"این‌ها قلعه/شهرِ شناخته‌شده‌ای در بازی نیستند: {'، '.join(bad)}")
    occupied = set()
    async for row in players.find({}, {"castle": 1, "castle_buildings": 1}):
        if row.get("castle"):
            occupied.add(row["castle"])
        occupied.update((row.get("castle_buildings") or {}).keys())
    if any(castle in occupied for castle in requested):
        raise HTTPException(409, "یکی از قلعه‌های انتخاب‌شده قبلاً گرفته شده؛ فهرست را تازه کن")
    state = await registration_state()
    region_by_castle = await castle_region_map()
    if any(state.get(region_by_castle.get(castle), {}).get("full") for castle in requested):
        raise HTTPException(409, "ظرفیت ثبت‌نام یکی از اقلیم‌های انتخاب‌شده تکمیل شده است")

    doc = {
        "tg_id": user["id"],
        "telegram_username": user.get("username"),
        "name": body.name.strip()[:40],
        "gender": body.gender,
        "title": DEFAULT_TITLE[body.gender],
        "region": None,
        "castle": None,
        "is_port": False,
        "requested_castles": requested,
        "backstory": body.backstory.strip(),
        "profile_image": body.profile_image,
        "resources": rule("economy.starting_resources", STARTING_RESOURCES),
        "troops": {},
        "buildings": {},
        "points": 100,
        "popularity": POPULARITY_START,
        "tax_rate": int(rule("tax.default_rate", TAX_RATE_DEFAULT)),
        "alliance_count": 0,
        "last_feast": None,
        "created_at": now(),
        "last_tick": now(),
        "stats": normalize_stats({}), "medals": {},
    }
    if existing:
        changed = await players.replace_one({"tg_id": user["id"], "registration_reset": True}, doc)
        if not changed.matched_count:
            raise HTTPException(409, "درخواست قبلاً ثبت شده است")
    else:
        await players.insert_one(doc)
    requested_text = "، ".join(requested) if requested else "بدون اولویت قلعه"
    await notify_admins(
        "new_player",
        "👤 بازیکن تازه منتظر تخصیص است",
        f"{doc['name']} ثبت‌نام کرد. انتخاب‌های قلعه: {requested_text}",
        dedupe_key=f"new-player:{user['id']}",
        priority="normal",
        player_name=doc["name"],
        player_tg_id=user["id"],
        action="از پنل ادمین ← ثبت‌نام، اقلیم و قلعه را مشخص کن.",
        audience_roles=("owner", "full"),
    )
    return {"ok": True}


@router.get("/registration-options")
async def get_registration_options(user: dict = Depends(get_user)):
    return {"regions": list((await registration_state()).values())}

@router.get("/me")
async def me(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    admin_role = await get_admin_role(user)
    if admin_role:
        # ادمین عضو رقابت نیست و قلعه ندارد، اما یک مدل نمایشی کامل می‌گیرد تا
        # بتواند همهٔ صفحات معمول اپ را برای نظارت باز کند.
        profile = p or {}
        return {
            "registered": True, "pending": False, "admin_spectator": True,
            "name": profile.get("name", user.get("first_name", "ادمین")),
            "backstory": profile.get("backstory", ""), "profile_image": profile.get("profile_image"),
            "gender": profile.get("gender", "lord"), "title": "ادمین",
            "admin_role": admin_role, "is_owner": admin_role == "owner",
            "rank_label": None, "region": None, "region_name": "بدون اقلیم",
            "castle": None, "castles": [], "house": None, "is_port": False,
            "resources": {key: 0 for key in STARTING_RESOURCES}, "resource_caps": {},
            "active_campaigns": 0, "points": 0, "alliance_count": 0,
            "popularity": 0, "medals": [], "stats": normalize_stats({}),
            "tax_rate": 0, "rank": None, "total_players": len(await scored_players()),
            "day": 1, "season_length": SEASON_LENGTH_DAYS,
        }
    if not p:
        return {"registered": False}
    if p.get("is_dead"):
        return {"registered": True, "is_dead": True, "name": p["name"], "death_reason": p.get("death_reason")}
    if p.get("registration_reset"):
        return {"registered": False}
    # username بدون فرم و دخالت بازیکن از initData معتبر تلگرام تازه نگه داشته می‌شود.
    # اگر کاربر username خود را عوض یا حذف کند، پنل ادمین نیز با ورود بعدی او اصلاح می‌شود.
    current_username = (user.get("username") or "").strip().lstrip("@") or None
    if p.get("telegram_username") != current_username:
        if current_username:
            await players.update_one({"tg_id": user["id"]}, {"$set": {"telegram_username": current_username}})
        else:
            await players.update_one({"tg_id": user["id"]}, {"$unset": {"telegram_username": ""}})
        p["telegram_username"] = current_username
    if not p.get("region") or not p.get("castle"):
        return {
            "registered": True, "pending": True,
            "name": p["name"], "gender": p.get("gender", "lord"),
            "title": p.get("title", DEFAULT_TITLE.get(p.get("gender", "lord"))),
            "admin_role": await get_admin_role(user),
            "is_owner": admin_role == "owner",
        }
    # پیمان‌ها در هر بازدید دوباره محاسبه می‌شوند تا رسیدن به روز هفتم/دهم
    # بدون نیاز به عملیات تازه، مدال را خودکار ارتقا دهد.
    stats = normalize_stats(p)
    seven_days = ten_days = accepted_count = 0
    async for pact in alliances.find({"$or": [{"from_id": user["id"]}, {"to_id": user["id"]}]}):
        started = pact.get("accepted_at")
        if not started and pact.get("status") == "accepted":
            started = pact.get("created_at")
        if not started:
            continue
        accepted_count += 1
        ended = pact.get("ended_at") or now()
        duration_days = max(0, (ended - started).total_seconds() / 86400)
        seven_days += int(duration_days >= 7)
        ten_days += int(duration_days >= 10)
    stats["alliances_accepted"] = max(stats.get("alliances_accepted", 0), accepted_count)
    stats["alliances_7_days"] = seven_days
    stats["alliances_10_days"] = ten_days
    # ارتقاهایی که مهلتشون تمام شده رو اول نهایی می‌کنیم — وگرنه بازیکنی که فقط سر
    # می‌زنه بدون رفتن به تبِ ساختمان‌ها، تولید/سقفش رو با سطح قدیمی (پیش‌از-ارتقا)
    # می‌بینه، شاید تا خیلی بعد
    p = apply_production(p)
    p["resources"] = await apply_campaign_upkeep(user["id"], p["resources"])
    await players.update_one({"tg_id": user["id"]}, {"$set": production_fields(p)})
    season_start = p.get("season_started_at") or p["created_at"]
    day = min(SEASON_LENGTH_DAYS, (((now() - season_start).days % SEASON_LENGTH_DAYS) + 1))
    # موجودیِ واقعی تو دیتابیس اعشاریه (تا تولیدِ کم‌مقدار بینِ چک‌ها گم نشه) — برای
    # نمایش به بازیکن رند می‌شود
    display_resources = {k: (round(v) if isinstance(v, (int, float)) else v) for k, v in p["resources"].items()}

    rows = await scored_players()
    total = len(rows)
    rank = None   # ادمین‌ها در لیدربرد نیستند، پس رتبه‌ای هم ندارند
    score = 0
    rank_label = None
    for i, row in enumerate(rows):
        if row["player"]["tg_id"] == user["id"]:
            rank = i + 1
            score = row["score"]
            rank_label = row["rank_label"]
            break

    popularity = p.get("popularity", POPULARITY_START)
    active_campaigns = await campaigns.count_documents({"tg_id": user["id"], "active": True})
    return {
        "registered": True,
        "pending": False,
        "name": p["name"],
        "backstory": p.get("backstory", ""), "profile_image": p.get("profile_image"),
        "admin_role": admin_role,
        "is_owner": admin_role == "owner",
        "gender": p.get("gender", "lord"),
        "title": p.get("title", DEFAULT_TITLE.get(p.get("gender", "lord"))),
        "rank_label": rank_label,
        "region": p["region"],
        "region_name": REGIONS[p["region"]]["name"],
        "castle": p["castle"],
        "castles": list(p.get("castle_buildings", {}).keys()),
        "house": p.get("house") or CASTLE_HOUSES.get(p["castle"]),
        "is_port": p["is_port"],
        "resources": display_resources,
        "resource_caps": effective_caps(p),
        "active_campaigns": active_campaigns,
        "points": score,
        "alliance_count": p.get("alliance_count", 0),
        "popularity": popularity,
        "medals": medal_rows(p),
        "stats": normalize_stats(p),
        "tax_rate": p.get("tax_rate", TAX_RATE_DEFAULT),
        "rank": rank, "total_players": total,
        "day": day, "season_length": SEASON_LENGTH_DAYS,
    }

@router.get("/{tg_id}/castles")
async def player_castles(tg_id: int, user: dict = Depends(get_user)):
    """همهٔ قلعه‌های یک بازیکن (خانگی + هر قلعهٔ اضافه‌ای که فتح کرده) — برای انتخابِ
    مبدا/مقصدِ کاروان وقتی طرفِ مقابل چند قلعه داره؛ مالکیتِ قلعه‌ها هرحال از رویِ
    نقشه هم برای همه دیده می‌شه، پس افشای عمومی‌اش مشکلی نداره"""
    p = await players.find_one({"tg_id": tg_id})
    if not p:
        raise HTTPException(404, "بازیکن پیدا نشد")
    return owned_castles(p)

@router.get("/search")
async def search(q: str = "", user: dict = Depends(get_user)):
    """جست‌وجوی لردها بر اساس نام یا قلعه — برای انتخاب گیرندهٔ کلاغ/پیمان"""
    q = q.strip()
    if len(q) < 2:
        return []
    pattern = re.escape(q)
    cur = players.find(
        {"tg_id": {"$ne": user["id"]}, "$or": [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"castle": {"$regex": pattern, "$options": "i"}},
        ]},
        {"tg_id": 1, "name": 1, "castle": 1, "region": 1, "title": 1},
    ).limit(20)
    return [{
        "tg_id": p["tg_id"], "name": p["name"], "castle": p["castle"],
        "region_name": REGIONS.get(p["region"], {}).get("name", p["region"]),
        "title": p.get("title"),
    } async for p in cur]

class TaxBody(BaseModel):
    rate: int

@router.post("/tax")
async def set_tax(body: TaxBody, user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        raise HTTPException(403, "اول ثبت‌نام کن")
    p = apply_production(p)
    p["resources"] = await apply_campaign_upkeep(user["id"], p["resources"])
    if not (0 <= body.rate <= 100):
        raise HTTPException(400, "نرخ مالیات باید بین ۰ تا ۱۰۰ درصد باشد")
    fields = production_fields(p)
    fields.update({"tax_rate": body.rate, "stats": normalize_stats(p), "medals": sync_medals(p)})
    await players.update_one({"tg_id": user["id"]}, {"$set": fields})
    return {"ok": True, "tax_rate": body.rate}
