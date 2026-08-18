import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user, get_admin_role
from db import players, campaigns, alliances
from game import now, apply_production, effective_caps, owned_castles, resolve_building_upgrades
from medals import medal_rows, normalize_stats, sync_medals
from game_data import REGIONS, CASTLE_HOUSES
from config import STARTING_RESOURCES, SEASON_LENGTH_DAYS, POPULARITY_START, TAX_RATE_DEFAULT, DEFAULT_TITLE, max_tax_rate, OWNER_ID
from ranks import scored_players
from routers.war import apply_campaign_upkeep, all_castle_names_and_ports

router = APIRouter(prefix="/api/players", tags=["players"])

MAX_REQUESTED_CASTLES = 5

class RegisterBody(BaseModel):
    name: str
    gender: str   # "lord" | "lady"
    requested_castles: list[str] = []   # اولویتِ خودِ بازیکن — چون ممکنه اولی‌ها قبلاً اشغال شده باشن

@router.post("/register")
async def register(body: RegisterBody, user: dict = Depends(get_user)):
    """فقط نام، جنسیت، و لیستِ اولویتیِ خاندان‌های درخواستی — خودِ تخصیصِ نهاییِ
    اقلیم/قلعه رو ادمین بعداً از پنلش دستی انجام می‌ده"""
    if body.gender not in DEFAULT_TITLE:
        raise HTTPException(400, "جنسیت نامعتبر")
    if not body.name.strip():
        raise HTTPException(400, "نام نمی‌تواند خالی باشد")
    if await players.find_one({"tg_id": user["id"]}):
        raise HTTPException(409, "قبلاً ثبت‌نام کرده‌ای")

    requested = list(dict.fromkeys(c.strip() for c in body.requested_castles if c.strip()))[:MAX_REQUESTED_CASTLES]
    if requested:
        names, _ports = await all_castle_names_and_ports()
        bad = [c for c in requested if c not in names]
        if bad:
            raise HTTPException(400, f"این‌ها قلعه/شهرِ شناخته‌شده‌ای در بازی نیستند: {'، '.join(bad)}")

    doc = {
        "tg_id": user["id"],
        "name": body.name.strip()[:40],
        "gender": body.gender,
        "title": DEFAULT_TITLE[body.gender],
        "region": None,
        "castle": None,
        "is_port": False,
        "requested_castles": requested,
        "resources": dict(STARTING_RESOURCES),
        "troops": {},
        "buildings": {},
        "points": 100,
        "popularity": POPULARITY_START,
        "tax_rate": TAX_RATE_DEFAULT,
        "alliance_count": 0,
        "last_feast": None,
        "created_at": now(),
        "last_tick": now(),
        "stats": normalize_stats({}), "medals": {},
    }
    await players.insert_one(doc)
    return {"ok": True}

@router.get("/me")
async def me(user: dict = Depends(get_user)):
    p = await players.find_one({"tg_id": user["id"]})
    if not p:
        return {"registered": False}
    if not p.get("region") or not p.get("castle"):
        return {
            "registered": True, "pending": True,
            "name": p["name"], "gender": p.get("gender", "lord"),
            "title": p.get("title", DEFAULT_TITLE.get(p.get("gender", "lord"))),
            "admin_role": await get_admin_role(user),
            "is_owner": user["id"] == OWNER_ID,
        }
    # ارتقاهایی که مهلتشون تمام شده رو اول نهایی می‌کنیم — وگرنه بازیکنی که فقط سر
    # می‌زنه بدون رفتن به تبِ ساختمان‌ها، تولید/سقفش رو با سطح قدیمی (پیش‌از-ارتقا)
    # می‌بینه، شاید تا خیلی بعد
    p = resolve_building_upgrades(p)
    p = apply_production(p)
    p["resources"] = await apply_campaign_upkeep(user["id"], p["resources"])
    await players.update_one({"tg_id": user["id"]}, {"$set": {
        "resources": p["resources"], "last_tick": p["last_tick"],
        "buildings": p["buildings"], "castle_buildings": p.get("castle_buildings", {}),
    }})
    day = min(SEASON_LENGTH_DAYS, ( (now() - p["created_at"]).days % SEASON_LENGTH_DAYS ) + 1)
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
    admin_role = await get_admin_role(user)
    active_campaigns = await campaigns.count_documents({"tg_id": user["id"], "active": True})
    return {
        "registered": True,
        "pending": False,
        "name": p["name"],
        "admin_role": admin_role,
        "is_owner": user["id"] == OWNER_ID,
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
        "tax_rate": p.get("tax_rate", TAX_RATE_DEFAULT),
        "max_tax_rate": max_tax_rate(popularity),
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
    cap = max_tax_rate(p.get("popularity", POPULARITY_START))
    if not (0 <= body.rate <= cap):
        raise HTTPException(400, f"نرخ مالیات باید بین ۰ تا {cap} درصد باشد")
    await players.update_one({"tg_id": user["id"]},
        {"$set": {"tax_rate": body.rate, "resources": p["resources"], "last_tick": p["last_tick"],
                  "stats": normalize_stats(p), "medals": sync_medals(p)}})
    return {"ok": True, "tax_rate": body.rate}
